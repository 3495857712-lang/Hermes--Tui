"""Prompt construction for the Hermes agent.

The :class:`PromptBuilder` assembles the system prompt from the SOUL
persona, available tools, memory summary, matched skills, and current time.
It also provides helpers for building message lists and compressing
history when approaching the context window.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from .llm import LLMMessage
from .memory import MemoryManager
from .skills import Skill, SkillLoader
from .utils.helpers import approx_token_count

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Build prompts and message lists for LLM requests."""

    def __init__(
        self,
        soul_content: str,
        memory_manager: MemoryManager | None = None,
        skill_loader: SkillLoader | None = None,
        extra_system_prompt: str = "",
    ) -> None:
        """Initialise the prompt builder.

        Args:
            soul_content: The SOUL persona text.
            memory_manager: Optional memory manager for context injection.
            skill_loader: Optional skill loader for skill injection.
            extra_system_prompt: Additional system-prompt text from config.
        """
        self.soul_content = soul_content
        self.memory = memory_manager
        self.skills = skill_loader
        self.extra_system_prompt = extra_system_prompt

    def build_system_prompt(
        self,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Assemble the full system prompt.

        Args:
            available_tools: OpenAI function schemas to describe.

        Returns:
            The complete system prompt string.
        """
        sections: list[str] = [self.soul_content.strip()]

        if self.extra_system_prompt.strip():
            sections.append(self.extra_system_prompt.strip())

        if available_tools:
            tool_lines = ["## Available tools"]
            for tool in available_tools:
                fn = tool.get("function", {})
                tool_lines.append(
                    f"- **{fn.get('name', '')}**: "
                    f"{fn.get('description', '')}"
                )
            sections.append("\n".join(tool_lines))

        if self.memory is not None:
            summary = self.memory.get_context_summary()
            if summary:
                sections.append("## Memory\n" + summary)

        if self.skills is not None:
            all_skills = self.skills.list_skills()
            if all_skills:
                skill_lines = ["## Available skills"]
                for s in all_skills:
                    meta = self.skills.get_metadata(s)
                    skill_lines.append(
                        f"- **{meta['name']}**: {meta['description']}"
                    )
                sections.append("\n".join(skill_lines))

        now = datetime.now(UTC)
        sections.append(
            f"## Current time\n{now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        return "\n\n".join(sections)

    def build_messages(
        self,
        history: list[LLMMessage],
        user_input: str,
        matched_skills: list[Skill] | None = None,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM request.

        Args:
            history: Prior messages in the session.
            user_input: The latest user message.
            matched_skills: Skills relevant to the current turn; their
                tier-2 descriptions are injected into the user message.
            available_tools: Tool schemas (used in system prompt only).

        Returns:
            A list of message dicts ready for the API.
        """
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self.build_system_prompt(available_tools),
            }
        ]

        for msg in history:
            if msg.content or msg.tool_calls:
                messages.append(msg.to_dict())

        content_parts = [user_input]
        if matched_skills and self.skills is not None:
            skill_contexts: list[str] = []
            for skill in matched_skills:
                desc = self.skills.get_description(skill)
                skill_contexts.append(
                    f"### Skill: {desc['name']}\n"
                    f"{desc['description']}\n"
                    f"Tags: {', '.join(desc.get('tags', []))}"
                )
            if skill_contexts:
                content_parts.append(
                    "\n\n<related-skills>\n"
                    + "\n\n".join(skill_contexts)
                    + "\n</related-skills>"
                )

        messages.append({"role": "user", "content": "\n".join(content_parts)})
        return messages

    @staticmethod
    def format_tool_result(
        tool_call_id: str, result: str
    ) -> dict[str, str]:
        """Format a tool execution result as a chat message.

        Args:
            tool_call_id: The ID of the tool call this responds to.
            result: The string output from the tool.

        Returns:
            A message dict with role ``tool``.
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    def compress_messages(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> list[dict[str, Any]]:
        """Compress message history to fit within *max_tokens*.

        Strategy: always keep the system message and the most recent
        messages.  Middle messages are summarised into a single note.

        Args:
            messages: The full message list.
            max_tokens: Approximate token budget.

        Returns:
            A compressed message list.
        """
        if not messages:
            return messages

        total = sum(
            approx_token_count(m.get("content", "")) for m in messages
        )
        if total <= max_tokens:
            return messages

        system_msg = (
            messages[0] if messages[0].get("role") == "system" else None
        )
        conversation = messages[1:] if system_msg else messages

        keep_last = max(4, len(conversation) // 3)
        middle = (
            conversation[:-keep_last]
            if len(conversation) > keep_last
            else []
        )
        tail = conversation[-keep_last:]

        result: list[dict[str, Any]] = []
        if system_msg:
            result.append(system_msg)

        if middle:
            summary_lines = [
                f"- [{m.get('role', '?')}] "
                f"{(m.get('content') or '')[:120]}"
                for m in middle
            ]
            result.append(
                {
                    "role": "system",
                    "content": (
                        "Earlier conversation summary (compressed):\n"
                        + "\n".join(summary_lines)
                    ),
                }
            )

        result.extend(tail)
        logger.info(
            "Compressed messages: %d -> %d",
            len(messages),
            len(result),
        )
        return result

    @staticmethod
    def count_tokens_approx(text: str) -> int:
        """Return an approximate token count for *text* (~4 chars/token)."""
        return approx_token_count(text)


# ----------------------------------------------------------------------
# Module-level functional API (back-compat / convenience wrappers)
# ----------------------------------------------------------------------

_DEFAULT_SOUL = (
    "You are Hermes, a self-improving local-first AI assistant. "
    "You think carefully, use tools when helpful, and reflect on your "
    "actions so you can grow over time."
)


def build_system_prompt(
    soul: str = _DEFAULT_SOUL,
    tools_description: str = "",
    memory_summary: str = "",
    skills_description: str = "",
    extra: str = "",
) -> str:
    """Assemble a system prompt string from named sections."""
    sections = [soul.strip()]
    if tools_description.strip():
        sections.append("## Available tools\n" + tools_description.strip())
    if memory_summary.strip():
        sections.append("## Memory\n" + memory_summary.strip())
    if skills_description.strip():
        sections.append("## Available skills\n" + skills_description.strip())
    if extra.strip():
        sections.append(extra.strip())
    now = datetime.now(UTC)
    sections.append(f"## Current time\n{now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return "\n\n".join(s for s in sections if s)


def build_messages(
    user_message: str,
    system_prompt: str,
    history: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build ``[system, ...history, user]`` message dicts."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in history or []:
        if isinstance(msg, dict):
            messages.append(msg)
        elif hasattr(msg, "to_dict"):
            messages.append(msg.to_dict())
        else:
            messages.append({"role": getattr(msg, "role", "user"),
                             "content": getattr(msg, "content", str(msg))})
    messages.append({"role": "user", "content": user_message})
    return messages


def format_tool_result(
    tool_call_id: str,
    result: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Return a tool-role message dict."""
    msg: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": result,
    }
    if name:
        msg["name"] = name
    return msg


def count_tokens(messages: list[Any]) -> int:
    """Approximate total tokens for a list of message dicts/LLMMessage."""
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            total += approx_token_count(msg.get("content", ""))
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                total += approx_token_count(fn.get("arguments", ""))
        elif hasattr(msg, "content"):
            total += approx_token_count(getattr(msg, "content", ""))
    return total


def compress_messages(
    messages: list[dict[str, Any]],
    max_tokens: int = 3000,
    keep_recent: int = 6,
) -> list[dict[str, Any]]:
    """Compress history to fit within *max_tokens*, preserving system + tail."""
    if not messages:
        return messages
    if count_tokens(messages) <= max_tokens:
        return list(messages)

    system = messages[0] if messages[0].get("role") == "system" else None
    rest = messages[1:] if system else list(messages)

    keep = max(1, keep_recent)
    if len(rest) <= keep:
        return list(messages)

    middle = rest[:-keep]
    tail = rest[-keep:]
    summary_lines = [
        f"- [{m.get('role', '?')}] {(m.get('content') or '')[:120]}"
        for m in middle
    ]
    result: list[dict[str, Any]] = []
    if system:
        result.append(system)
    result.append({
        "role": "system",
        "content": "Earlier conversation summary (compressed):\n"
                   + "\n".join(summary_lines),
    })
    result.extend(tail)

    # If still too big, drop the summary
    if count_tokens(result) > max_tokens:
        result = ([system] if system else []) + tail
    return result
