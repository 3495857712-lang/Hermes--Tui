"""Tests for hermes_tui.agent module."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hermes_tui.agent import AIAgent
from hermes_tui.llm import LLMResponse


def _tool_call_response(
    tool_name: str,
    arguments: str = "{}",
    call_id: str = "call_1",
    content: str = "",
) -> LLMResponse:
    """Build an LLMResponse containing a tool call."""
    return LLMResponse(
        content=content,
        tool_calls=[
            {
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": arguments},
            }
        ],
        finish_reason="tool_calls",
    )


def _text_response(text: str) -> LLMResponse:
    """Build a simple text-only LLMResponse."""
    return LLMResponse(content=text, finish_reason="stop")


class TestSessionManagement:
    """Tests for session creation, listing, and deletion."""

    async def test_create_session(self, agent: AIAgent) -> None:
        """Creating a session should return a valid ID and persist it."""
        session_id = agent.create_session(title="Test")
        assert session_id
        session = agent.get_session(session_id)
        assert session is not None
        assert session["title"] == "Test"

    async def test_list_sessions(self, agent: AIAgent) -> None:
        """Multiple sessions should all appear in the list."""
        agent.create_session("A")
        agent.create_session("B")
        sessions = agent.list_sessions()
        assert len(sessions) == 2

    async def test_delete_session(self, agent: AIAgent) -> None:
        """Deleting a session should remove it and its messages."""
        sid = agent.create_session("To delete")
        await agent.send_message_simple(sid, "Hello")
        assert agent.delete_session(sid) is True
        assert agent.get_session(sid) is None

    async def test_session_save_and_load(self, agent: AIAgent) -> None:
        """After a conversation, loading the session should restore history."""
        sid = agent.create_session("Persistent")
        await agent.send_message_simple(sid, "Remember this")

        agent._sessions.pop(sid, None)

        rows = agent.load_session(sid)
        assert len(rows) >= 2
        roles = [r["role"] for r in rows]
        assert "user" in roles
        assert "assistant" in roles

    async def test_session_title(self, agent: AIAgent, mock_llm_client: MagicMock) -> None:
        """The session title should be set to the first 30 chars of the first message."""
        long_message = "This is a very long first message that exceeds thirty characters"
        sid = agent.create_session()
        mock_llm_client.chat = AsyncMock(return_value=_text_response("Reply"))
        await agent.send_message_simple(sid, long_message)

        session = agent.get_session(sid)
        assert session is not None
        assert session["title"] == long_message[:30]
        assert len(session["title"]) == 30


class TestSendMessage:
    """Tests for sending messages and receiving responses."""

    async def test_send_message_simple(self, agent: AIAgent, mock_llm_client: MagicMock) -> None:
        """A simple conversation without tool calls should stream text back."""
        mock_llm_client.chat = AsyncMock(return_value=_text_response("Hello! How can I help?"))
        sid = agent.create_session()
        response = await agent.send_message_simple(sid, "Hi there")
        assert "Hello" in response
        mock_llm_client.chat.assert_awaited()

    async def test_empty_message(self, agent: AIAgent, mock_llm_client: MagicMock) -> None:
        """An empty message should not be sent to the LLM."""
        mock_llm_client.chat = AsyncMock(return_value=_text_response("should not be called"))
        sid = agent.create_session()
        response = await agent.send_message_simple(sid, "")
        assert response == ""
        mock_llm_client.chat.assert_not_called()

    async def test_conversation_history(self, agent: AIAgent, mock_llm_client: MagicMock) -> None:
        """Multi-turn conversations should accumulate history correctly."""
        mock_llm_client.chat = AsyncMock(
            side_effect=[
                _text_response("First answer"),
                _text_response("Second answer"),
            ]
        )
        sid = agent.create_session()
        await agent.send_message_simple(sid, "Question 1")
        await agent.send_message_simple(sid, "Question 2")

        history = agent._get_history(sid)
        assert len(history) == 4
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[2].role == "user"
        assert history[3].role == "assistant"


class TestToolCalling:
    """Tests for the agent's tool-use loop."""

    async def test_send_message_with_tool_call(
        self, agent: AIAgent, mock_llm_client: MagicMock
    ) -> None:
        """When LLM returns a tool call, the agent should execute it and continue."""
        mock_llm_client.chat = AsyncMock(
            side_effect=[
                _tool_call_response("get_time", call_id="call_time"),
                _text_response("The current time is shown above."),
            ]
        )
        sid = agent.create_session()
        response = await agent.send_message_simple(sid, "What time is it?")

        assert mock_llm_client.chat.await_count == 2
        assert "time" in response.lower() or "shown" in response.lower()

        history = agent._get_history(sid)
        roles = [m.role for m in history]
        assert "tool" in roles

    async def test_max_tool_iterations(self, agent: AIAgent, mock_llm_client: MagicMock) -> None:
        """The agent should stop after max_tool_iterations."""
        mock_llm_client.chat = AsyncMock(
            side_effect=[
                _tool_call_response("get_time", call_id=f"call_{i}")
                for i in range(agent.max_tool_iterations + 2)
            ]
        )
        sid = agent.create_session()
        response = await agent.send_message_simple(sid, "Keep calling tools")

        assert mock_llm_client.chat.await_count == agent.max_tool_iterations
        assert "maximum tool iterations" in response.lower()

    async def test_tool_execution_error_handling(
        self, agent: AIAgent, mock_llm_client: MagicMock
    ) -> None:
        """When a tool execution raises an error, the agent should continue with an error result."""

        async def mock_execute(name: str, **kwargs: Any) -> str:
            return f"Error executing tool '{name}': something went wrong"

        agent.tools.execute = mock_execute  # type: ignore[method-assign]

        mock_llm_client.chat = AsyncMock(
            side_effect=[
                _tool_call_response("failing_tool", call_id="call_fail"),
                _text_response("The tool failed, but I'm still here."),
            ]
        )
        sid = agent.create_session()
        response = await agent.send_message_simple(sid, "Use the failing tool")

        assert "still here" in response
        assert mock_llm_client.chat.await_count == 2


class TestMemoryExtraction:
    """Tests for asynchronous memory extraction from conversations."""

    async def test_agent_extracts_memory(self, agent: AIAgent, mock_llm_client: MagicMock) -> None:
        """After a conversation containing '记住', a memory should be stored."""
        mock_llm_client.chat = AsyncMock(return_value=_text_response("好的，我记住了。"))
        sid = agent.create_session()
        await agent.send_message_simple(sid, "记住：我喜欢喝咖啡")

        await asyncio.sleep(0.2)

        memories = agent.memory.search("咖啡")
        assert len(memories) >= 1
