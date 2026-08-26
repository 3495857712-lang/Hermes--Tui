"""LLM client abstraction and OpenAI-compatible implementation.

This module defines the message/response data models, a small hierarchy
of typed exceptions, and an :class:`LLMClient` that speaks the OpenAI
Chat Completions API (also used by Ollama, vLLM, LM Studio, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import LLMConfig
from .exceptions import (
    AuthenticationError,
    BadRequestError,
    LLMError,
    RateLimitError,
    ServerError,
)
from .exceptions import (
    ConnectionError as LLMConnectionError,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------

@dataclass
class LLMMessage:
    """A chat message sent to or received from the LLM."""

    role: str
    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None
    name: str | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the JSON-serialisable dict expected by the API."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            msg["name"] = self.name
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            normalized: list[dict[str, Any]] = []
            for tc in self.tool_calls:
                if isinstance(tc, dict):
                    entry: dict[str, Any] = {}
                    # Preserve original keys in original order.
                    for k, v in tc.items():
                        if k == "function":
                            fn = v
                            raw_args = fn.get("arguments", "{}")
                            if isinstance(raw_args, dict):
                                raw_args = json.dumps(raw_args, ensure_ascii=False)
                            entry["function"] = {
                                "name": fn.get("name", ""),
                                "arguments": raw_args,
                            }
                        else:
                            entry[k] = v
                    normalized.append(entry)
                else:  # pragma: no cover - defensive
                    normalized.append(tc)  # type: ignore[arg-type]
            msg["tool_calls"] = normalized
        return msg

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMMessage:
        """Build an LLMMessage from a dict (inverse of :meth:`to_dict`)."""
        raw_calls = data.get("tool_calls")
        tool_calls: list[dict[str, Any]] | None = None
        if raw_calls:
            tool_calls = []
            for tc in raw_calls:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", "{}")
                    if isinstance(raw_args, str):
                        try:
                            args: Any = json.loads(raw_args) if raw_args.strip() else {}
                        except json.JSONDecodeError:
                            args = {"_raw": raw_args}
                    else:
                        args = raw_args or {}
                    tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {"name": fn.get("name", ""), "arguments": args},
                    })
        return cls(
            role=data["role"],
            content=data.get("content") or "",
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=tool_calls,
        )


@dataclass
class LLMResponse:
    """A structured LLM completion response."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """True when the model requested at least one tool call."""
        return bool(self.tool_calls)


__all__ = [
    "AuthenticationError",
    "BadRequestError",
    "LLMClient",
    "LLMConnectionError",
    "LLMError",
    "LLMMessage",
    "LLMResponse",
    "RateLimitError",
    "ServerError",
    "create_client",
]


# ------------------------------------------------------------------
# Client
# ------------------------------------------------------------------

_RETRYABLE_STATUS = {500, 502, 503, 504}
_BACKOFF_BASE = 0.5


class LLMClient:
    """Client for OpenAI-compatible Chat Completions endpoints."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        cfg = config or LLMConfig()
        self.config = cfg
        self.base_url = (base_url or cfg.base_url).rstrip("/")
        self.model = model or cfg.model
        self.temperature = temperature if temperature is not None else cfg.temperature
        self.max_tokens = max_tokens if max_tokens is not None else cfg.max_tokens
        self._max_retries = max_retries if max_retries is not None else cfg.max_retries
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or cfg.api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout if timeout is not None else cfg.timeout,
        )
        logger.info(
            "LLMClient initialised: base_url=%s model=%s",
            self.base_url, self.model,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        return payload

    @staticmethod
    def _parse_tool_calls(
        raw_tool_calls: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not raw_tool_calls:
            return result
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    arguments = {"_raw": raw_args}
            else:
                arguments = raw_args or {}
            result.append({
                "id": tc.get("id", ""),
                "type": tc.get("type", "function"),
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": arguments,
                },
            })
        return result

    @staticmethod
    def _classify_error(status_code: int, body: str) -> LLMError:
        if status_code == 401:
            return AuthenticationError(f"Authentication failed (401): {body}")
        if status_code == 429:
            return RateLimitError(f"Rate limited (429): {body}")
        if status_code == 400:
            return BadRequestError(f"Bad request (400): {body}")
        if status_code in _RETRYABLE_STATUS:
            return ServerError(f"Server error ({status_code}): {body}")
        return LLMError(f"Unexpected error ({status_code}): {body}")

    async def _post_with_retry(
        self, url: str, payload: dict[str, Any]
    ) -> httpx.Response:
        attempts = self._max_retries
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = await self._client.post(url, json=payload)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < attempts:
                    wait = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Network error (attempt %d/%d): %s - retrying",
                        attempt, attempts, exc,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise LLMConnectionError(
                    f"Connection failed after {attempts} attempts: {exc}"
                ) from exc

            if resp.status_code in _RETRYABLE_STATUS and attempt < attempts:
                wait = _BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Server %s (attempt %d/%d) - retrying",
                    resp.status_code, attempt, attempts,
                )
                await asyncio.sleep(wait)
                continue

            if resp.status_code >= 400:
                raise self._classify_error(resp.status_code, resp.text)
            return resp

        # Should not reach here under normal circumstances.
        if last_exc:
            raise LLMConnectionError(f"Request failed: {last_exc}")
        raise ServerError("Request failed without a response")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request and return the full response."""
        if stream:
            chunks: list[str] = []
            async for chunk in self.stream_chat(messages, tools, **kwargs):
                chunks.append(chunk)
            return LLMResponse(content="".join(chunks), model=self.model)

        payload = self._build_payload(messages, tools, stream=False, **kwargs)
        resp = await self._post_with_retry("/chat/completions", payload)
        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=self._parse_tool_calls(message.get("tool_calls")),
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model", self.model),
        )

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion, yielding text chunks."""
        payload = self._build_payload(messages, tools, stream=True, **kwargs)
        try:
            req = self._client.build_request("POST", "/chat/completions", json=payload)
            resp = await self._client.send(req, stream=True)
        except httpx.RequestError as exc:
            raise LLMConnectionError(
                f"Streaming connection failed: {exc}"
            ) from exc

        if resp.status_code >= 400:
            body = await resp.aread()
            raise self._classify_error(
                resp.status_code, body.decode("utf-8", "replace")
            )

        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            piece = delta.get("content")
            if piece:
                yield piece

        await resp.aclose()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def aclose(self) -> None:
        """Alias for :meth:`close`."""
        await self.close()


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

# Backwards-compatible alias.
OpenAICompatibleClient = LLMClient


class LLMClientFactory:
    """Create :class:`LLMClient` instances from configuration."""

    @staticmethod
    def create(config: LLMConfig) -> LLMClient:
        return LLMClient(config=config)


def create_client(config: LLMConfig) -> LLMClient:
    """Create an LLM client from configuration (convenience wrapper)."""
    return LLMClient(config=config)
