"""Tests for hermes_tui.llm module."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from hermes_tui.config import LLMConfig
from hermes_tui.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServerError,
)
from hermes_tui.exceptions import (
    ConnectionError as HermesConnectionError,
)
from hermes_tui.llm import LLMClient, LLMMessage, LLMResponse, create_client


def _make_config(**kwargs: Any) -> LLMConfig:
    """Create an LLMConfig with test defaults."""
    defaults = {
        "base_url": "http://localhost:11434/v1",
        "api_key": "test-key",
        "model": "test-model",
        "max_retries": 3,
    }
    defaults.update(kwargs)
    return LLMConfig(**defaults)


class TestModels:
    """Tests for LLMMessage and LLMResponse data models."""

    def test_message_model(self) -> None:
        """LLMMessage should serialize to and from dicts correctly."""
        msg = LLMMessage(role="user", content="Hello", name="alice")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert d["name"] == "alice"

        msg2 = LLMMessage.from_dict(d)
        assert msg2.role == "user"
        assert msg2.content == "Hello"

    def test_message_with_tool_calls(self) -> None:
        """LLMMessage should carry tool_calls."""
        tool_calls = [
            {"id": "call_1", "function": {"name": "x", "arguments": "{}"}}
        ]
        msg = LLMMessage(role="assistant", content="", tool_calls=tool_calls)
        d = msg.to_dict()
        assert d["tool_calls"] == tool_calls

    def test_response_model(self) -> None:
        """LLMResponse should track content, tool_calls, and usage."""
        resp = LLMResponse(
            content="Hi",
            model="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
        )
        assert resp.content == "Hi"
        assert resp.has_tool_calls is False
        assert resp.usage["prompt_tokens"] == 10

    def test_response_has_tool_calls(self) -> None:
        """has_tool_calls should be True when tool_calls is non-empty."""
        resp = LLMResponse(
            content="",
            tool_calls=[
                {"id": "1", "function": {"name": "f", "arguments": "{}"}}
            ],
        )
        assert resp.has_tool_calls is True


class TestChat:
    """Tests for the non-streaming chat() method."""

    @respx.mock
    async def test_openai_compatible_chat(self) -> None:
        """chat() should send a correctly formatted request and parse the response."""
        config = _make_config()
        client = LLMClient(config)

        expected_response = {
            "id": "chatcmpl-1",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello back!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8,
            },
        }

        route = respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=expected_response)
        )

        messages = [LLMMessage(role="user", content="Hello")]
        result = await client.chat(messages)

        assert route.called
        assert result.content == "Hello back!"
        assert result.model == "test-model"
        assert result.usage["total_tokens"] == 8
        assert result.finish_reason == "stop"

        request_body = json.loads(route.calls.last.request.content)
        assert request_body["model"] == "test-model"
        assert request_body["messages"][0]["content"] == "Hello"
        assert "temperature" in request_body

        await client.close()

    @respx.mock
    async def test_tool_call_parsing(self) -> None:
        """chat() should parse tool_calls from the response."""
        config = _make_config()
        client = LLMClient(config)

        tool_calls = [
            {
                "id": "call_abc",
                "type": "function",
                "function": {
                    "name": "get_time",
                    "arguments": "{}",
                },
            }
        ]
        response = {
            "model": "test-model",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {},
        }
        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=response)
        )

        result = await client.chat(
            [LLMMessage(role="user", content="What time?")]
        )
        assert result.has_tool_calls is True
        assert result.tool_calls[0]["function"]["name"] == "get_time"
        assert result.finish_reason == "tool_calls"

        await client.close()

    @respx.mock
    async def test_custom_headers(self) -> None:
        """Custom extra headers should be included in the request."""
        config = _make_config()
        client = LLMClient(
            config, extra_headers={"X-Custom-Header": "test-value"}
        )

        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "ok"}}
                    ],
                    "model": "test-model",
                    "usage": {},
                },
            )
        )

        await client.chat([LLMMessage(role="user", content="hi")])
        await client.close()


class TestErrorHandling:
    """Tests for HTTP error mapping to exceptions."""

    @respx.mock
    async def test_authentication_error(self) -> None:
        """A 401 response should raise AuthenticationError."""
        client = LLMClient(_make_config())
        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with pytest.raises(AuthenticationError):
            await client.chat([LLMMessage(role="user", content="hi")])
        await client.close()

    @respx.mock
    async def test_rate_limit_error(self) -> None:
        """A 429 response should raise RateLimitError."""
        client = LLMClient(_make_config())
        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        with pytest.raises(RateLimitError):
            await client.chat([LLMMessage(role="user", content="hi")])
        await client.close()

    @respx.mock
    async def test_bad_request_error(self) -> None:
        """A 400 response should raise BadRequestError."""
        client = LLMClient(_make_config())
        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        with pytest.raises(BadRequestError):
            await client.chat([LLMMessage(role="user", content="hi")])
        await client.close()

    @respx.mock
    async def test_server_error_retry(self) -> None:
        """A 5xx response should trigger a retry and eventually succeed."""
        client = LLMClient(_make_config(max_retries=3))

        route = respx.post(
            "http://localhost:11434/v1/chat/completions"
        ).mock(
            side_effect=[
                httpx.Response(500, text="Internal Server Error"),
                httpx.Response(502, text="Bad Gateway"),
                httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "recovered",
                                }
                            }
                        ],
                        "model": "test",
                        "usage": {},
                    },
                ),
            ]
        )

        result = await client.chat(
            [LLMMessage(role="user", content="hi")]
        )
        assert result.content == "recovered"
        assert route.call_count == 3
        await client.close()

    @respx.mock
    async def test_connection_error_retry(self) -> None:
        """A network connection error should trigger a retry."""
        client = LLMClient(_make_config(max_retries=3))

        route = respx.post(
            "http://localhost:11434/v1/chat/completions"
        ).mock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                httpx.ConnectError("Connection refused"),
                httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "ok",
                                }
                            }
                        ],
                        "model": "test",
                        "usage": {},
                    },
                ),
            ]
        )

        result = await client.chat(
            [LLMMessage(role="user", content="hi")]
        )
        assert result.content == "ok"
        assert route.call_count == 3
        await client.close()

    @respx.mock
    async def test_retry_exhausted(self) -> None:
        """After max retries with 5xx, the error should propagate."""
        client = LLMClient(_make_config(max_retries=3))

        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        with pytest.raises(ServerError):
            await client.chat([LLMMessage(role="user", content="hi")])
        await client.close()


class TestStreaming:
    """Tests for the stream_chat() method."""

    @respx.mock
    async def test_stream_chat_sse(self) -> None:
        """stream_chat should parse SSE chunks and yield text content."""
        config = _make_config()
        client = LLMClient(config)

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: {"choices":[{"delta":{"content":"!"}}]}',
            "data: [DONE]",
        ]
        stream_content = "\n".join(sse_lines)

        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                text=stream_content,
                headers={"content-type": "text/event-stream"},
            )
        )

        chunks: list[str] = []
        async for chunk in client.stream_chat(
            [LLMMessage(role="user", content="Hi")]
        ):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello world!"
        await client.close()

    @respx.mock
    async def test_stream_empty_response(self) -> None:
        """An empty stream should yield no chunks without error."""
        config = _make_config()
        client = LLMClient(config)

        respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                text="",
                headers={"content-type": "text/event-stream"},
            )
        )

        chunks: list[str] = []
        async for chunk in client.stream_chat(
            [LLMMessage(role="user", content="Hi")]
        ):
            chunks.append(chunk)

        assert chunks == []
        await client.close()


class TestClientFactory:
    """Tests for the create_client factory function."""

    def test_client_factory(self) -> None:
        """create_client should return an LLMClient instance."""
        config = _make_config(model="factory-model")
        client = create_client(config)
        assert isinstance(client, LLMClient)
        assert client.config.model == "factory-model"
