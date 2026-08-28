"""Core AI agent with sessions, tool use, and memory extraction."""

from __future__ import annotations

import asyncio
import json as _json
import logging
from collections.abc import AsyncIterator
from typing import Any

from hermes_tui.config import Config
from hermes_tui.database import DatabaseManager
from hermes_tui.llm import LLMClient, LLMMessage
from hermes_tui.memory import MemoryManager
from hermes_tui.prompt import build_messages, build_system_prompt
from hermes_tui.skills import SkillLoader
from hermes_tui.tools import ToolRegistry
from hermes_tui.utils.helpers import generate_id

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5
SESSION_TITLE_LENGTH = 30


class AIAgent:
    """Autonomous AI agent with conversation sessions, tools, and memory."""

    def __init__(
        self,
        config: Config,
        llm_client: LLMClient,
        memory_manager: MemoryManager,
        skill_loader: SkillLoader,
        tool_registry: ToolRegistry,
        db: DatabaseManager | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self.config = config
        self.llm = llm_client
        self.memory = memory_manager
        self.skills = skill_loader
        self.tools = tool_registry
        self.db = db or memory_manager.db
        self.max_tool_iterations = max_tool_iterations
        self._sessions: dict[str, list[LLMMessage]] = {}

    def create_session(self, title: str = "") -> str:
        """Create a new chat session and return its ID."""
        session_id = generate_id()
        self.db.create_session(session_id, title=title)
        self._sessions[session_id] = []
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve session metadata."""
        return self.db.get_session(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions."""
        return self.db.list_sessions()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        self._sessions.pop(session_id, None)
        return self.db.delete_session(session_id)

    def load_session(self, session_id: str) -> list[dict[str, Any]]:
        """Load session history from the database into memory."""
        rows = self.db.get_messages(session_id)
        messages = []
        for row in rows:
            msg = LLMMessage(
                role=row["role"],
                content=row.get("content", ""),
                tool_calls=row.get("tool_calls"),
                tool_call_id=row.get("tool_call_id"),
            )
            messages.append(msg)
        self._sessions[session_id] = messages
        return [dict(row) for row in rows]

    def _get_history(self, session_id: str) -> list[LLMMessage]:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def _build_system_prompt(self) -> str:
        memory_summary = self.memory.context_summary()
        skills_desc = "\n".join(
            f"- {s.name}: {s.description}" for s in self.skills.enabled_skills()[:10]
        )
        tools_desc = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in self.tools.list_tools()
        )
        return build_system_prompt(
            memory_summary=memory_summary,
            tools_description=tools_desc,
            skills_description=skills_desc,
        )

    async def send_message(self, session_id: str, content: str) -> AsyncIterator[str]:
        """Send a user message and stream the assistant response."""
        if not content or not content.strip():
            return

        history = self._get_history(session_id)

        session = self.db.get_session(session_id)
        if session and not session.get("title"):
            title = content.strip()[:SESSION_TITLE_LENGTH]
            self.db.update_session_title(session_id, title)

        user_msg = LLMMessage(role="user", content=content)
        history.append(user_msg)
        self.db.insert_message(
            message_id=generate_id(),
            session_id=session_id,
            role="user",
            content=content,
        )

        system_prompt = self._build_system_prompt()
        full_messages = build_messages(
            user_message=content,
            system_prompt=system_prompt,
            history=history[:-1],
        )
        llm_messages = [
            LLMMessage.from_dict(m) if isinstance(m, dict) else m for m in full_messages
        ]

        tool_schemas = self.tools.list_tools()

        for _iteration in range(self.max_tool_iterations):
            response = await self.llm.chat(
                messages=llm_messages,
                tools=tool_schemas if tool_schemas else None,
            )

            assistant_msg = LLMMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
            history.append(assistant_msg)

            if response.content:
                yield response.content

            self.db.insert_message(
                message_id=generate_id(),
                session_id=session_id,
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )

            if not response.has_tool_calls:
                break

            llm_messages.append(assistant_msg)

            for tool_call in response.tool_calls or []:
                fn = tool_call.get("function", {})
                tool_name = fn.get("name", "")
                tool_call_id = tool_call.get("id", generate_id())

                raw_args = fn.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        args = _json.loads(raw_args) if raw_args.strip() else {}
                    except (ValueError, TypeError):
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}

                result = await self.tools.execute(tool_name, **args)

                tool_msg = LLMMessage(
                    role="tool",
                    content=result,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
                history.append(tool_msg)
                llm_messages.append(tool_msg)

                self.db.insert_message(
                    message_id=generate_id(),
                    session_id=session_id,
                    role="tool",
                    content=result,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
        else:
            warning = "\n[Reached maximum tool iterations]"
            yield warning

        asyncio.create_task(self._extract_memories_async(session_id))

    async def _extract_memories_async(self, session_id: str) -> None:
        try:
            messages = self.db.get_messages(session_id)
            recent = messages[-10:]
            self.memory.extract_from_messages(recent)
        except Exception:
            logger.debug("Memory extraction failed", exc_info=True)

    async def send_message_simple(self, session_id: str, content: str) -> str:
        chunks: list[str] = []
        async for chunk in self.send_message(session_id, content):
            chunks.append(chunk)
        return "".join(chunks)
