"""Tests for hermes_tui.prompt module."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest

from hermes_tui.llm import LLMMessage
from hermes_tui.prompt import (
    build_messages,
    build_system_prompt,
    compress_messages,
    count_tokens,
    format_tool_result,
)


class TestBuildSystemPrompt:
    """Tests for system prompt assembly."""

    def test_build_system_prompt(self) -> None:
        """System prompt should include soul, tools, memory, and skills sections."""
        prompt = build_system_prompt(
            soul="You are a test assistant.",
            tools_description="- get_time: get current time",
            memory_summary="- User prefers dark mode",
            skills_description="- weather: check weather",
        )
        assert "test assistant" in prompt
        assert "get_time" in prompt
        assert "dark mode" in prompt
        assert "weather" in prompt

    def test_system_prompt_includes_date(self) -> None:
        """System prompt should contain the current UTC date."""
        prompt = build_system_prompt()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        assert today in prompt

    def test_default_soul(self) -> None:
        """When no soul is provided, the default SOUL should be used."""
        prompt = build_system_prompt()
        assert "Hermes" in prompt
        assert "self-improving" in prompt.lower()


class TestBuildMessages:
    """Tests for message list construction."""

    def test_build_messages(self) -> None:
        """build_messages should produce system + history + user message."""
        history = [
            LLMMessage(role="user", content="Previous question"),
            LLMMessage(role="assistant", content="Previous answer"),
        ]
        messages = build_messages(
            user_message="New question",
            system_prompt="You are helpful.",
            history=history,
        )
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["role"] == "assistant"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "New question"

    def test_build_messages_no_history(self) -> None:
        """With no history, only system and user message should appear."""
        messages = build_messages(
            user_message="Hello",
            system_prompt="System",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_build_messages_accepts_dict_history(self) -> None:
        """build_messages should accept plain dicts in history."""
        history = [{"role": "user", "content": "Hi"}]
        messages = build_messages(
            user_message="There",
            system_prompt="Sys",
            history=history,
        )
        assert messages[1]["content"] == "Hi"


class TestToolResult:
    """Tests for tool result message formatting."""

    def test_tool_result_format(self) -> None:
        """format_tool_result should produce a valid tool role message."""
        result = format_tool_result(
            tool_call_id="call_123",
            result="3:30 PM",
            name="get_time",
        )
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_123"
        assert result["content"] == "3:30 PM"
        assert result["name"] == "get_time"

    def test_tool_result_without_name(self) -> None:
        """format_tool_result should work without a name field."""
        result = format_tool_result(tool_call_id="call_1", result="ok")
        assert "name" not in result


class TestTokenCount:
    """Tests for approximate token counting."""

    def test_token_count_approx(self) -> None:
        """approx token count should be roughly len/4."""
        text = "a" * 40
        count = count_tokens([{"role": "user", "content": text}])
        assert count == 10

    def test_token_count_empty(self) -> None:
        """Empty content should contribute 0 tokens."""
        assert count_tokens([{"role": "user", "content": ""}]) == 0

    def test_token_count_with_tool_calls(self) -> None:
        """tool_calls should be included in token counting."""
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"arguments": "x" * 40}}],
        }
        count = count_tokens([msg])
        assert count >= 10

    def test_token_count_llm_message(self) -> None:
        """count_tokens should handle LLMMessage objects."""
        msg = LLMMessage(role="user", content="x" * 40)
        assert count_tokens([msg]) == 10


class TestCompressMessages:
    """Tests for message history compression."""

    def _make_long_history(self, n: int) -> list[dict]:
        """Create a history of n user/assistant pairs with long content."""
        messages: list[dict] = [{"role": "system", "content": "System prompt"}]
        for i in range(n):
            messages.append({"role": "user", "content": f"Question {i} " + "x" * 200})
            messages.append(
                {
                    "role": "assistant",
                    "content": f"Answer {i} " + "y" * 200,
                }
            )
        return messages

    def test_compress_messages(self) -> None:
        """Compression should reduce messages to fit within token budget."""
        messages = self._make_long_history(20)
        original_tokens = count_tokens(messages)

        compressed = compress_messages(messages, max_tokens=500, keep_recent=4)
        compressed_tokens = count_tokens(compressed)

        assert compressed_tokens <= 500 or len(compressed) <= 5
        assert compressed_tokens < original_tokens

    def test_compress_preserves_system(self) -> None:
        """The system message should always be retained after compression."""
        messages = self._make_long_history(15)
        compressed = compress_messages(messages, max_tokens=200, keep_recent=2)
        assert compressed[0]["role"] == "system"
        assert "System prompt" in compressed[0]["content"]

    def test_compress_preserves_recent(self) -> None:
        """The most recent messages should be retained after compression."""
        messages = self._make_long_history(15)
        compressed = compress_messages(messages, max_tokens=200, keep_recent=4)
        assert compressed[-1]["content"].startswith("Answer 14")

    def test_compress_short_history(self) -> None:
        """Short histories under the budget should not be modified."""
        messages = [
            {"role": "system", "content": "Sys"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        compressed = compress_messages(messages, max_tokens=10000, keep_recent=6)
        assert compressed == messages

    def test_compress_empty(self) -> None:
        """Compressing an empty list should return an empty list."""
        assert compress_messages([]) == []

    def test_compress_only_system(self) -> None:
        """Compressing a system-only message list should keep it."""
        messages = [{"role": "system", "content": "You are helpful."}]
        compressed = compress_messages(messages, max_tokens=10)
        assert len(compressed) == 1
        assert compressed[0]["role"] == "system"
