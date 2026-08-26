"""
Enhanced Agent — orchestration with Thought Graph, Memory Git,
Skill Forge, Reflection, Context Map, and Pipe Commands.

This is the core innovation layer: it wraps the basic LLM chat loop
with all the differentiating systems.  The agent doesn't just respond
to messages — it observes, reasons visibly, version-controls its own
memory, proposes improvements to itself, and lets the user inspect
and control every step.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .context_map import ContextMap, ContextSource
from .database import DatabaseManager
from .llm import LLMClient, LLMMessage, LLMResponse
from .memory import MemoryManager
from .memory_git import MemoryDiff, MemoryGit
from .pipe_commands import PipeCommandRegistry, PipeContext, default_registry
from .prompt import PromptBuilder
from .reflection import ReflectionEngine, TaskOutcome
from .skill_forge import SkillForge
from .skills import SkillLoader
from .thought_graph import NodeKind, ThoughtGraph
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class EnhancedSession:
    """A chat session with full innovation-layer state."""

    id: str
    title: str = "New Chat"
    messages: list[LLMMessage] = field(default_factory=list)
    thought_graph: ThoughtGraph = field(default_factory=ThoughtGraph)
    context_map: ContextMap | None = None
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class EnhancedAIAgent:
    """Agent with visible reasoning, version-controlled memory,
    self-evolving skills, and context introspection.

    This is the main entry point for Hermes TUI's differentiated
    experience.  It composes:

    - :class:`ThoughtGraph` — non-linear reasoning visualization
    - :class:`MemoryGit` — version-controlled memory
    - :class:`SkillForge` — self-evolution proposals
    - :class:`ReflectionEngine` — post-task reflection
    - :class:`ContextMap` — context window introspection
    - :class:`PipeCommandRegistry` — composable slash commands
    """

    def __init__(
        self,
        config: Config,
        llm_client: LLMClient,
        memory: MemoryManager,
        skills: SkillLoader,
        tools: ToolRegistry,
        prompt_builder: PromptBuilder,
        db: DatabaseManager | None = None,
        context_window_tokens: int = 8000,
    ) -> None:
        self.config = config
        self.llm = llm_client
        self.memory = memory
        self.skills = skills
        self.tools = tools
        self.prompt = prompt_builder
        self.db = db

        # Innovation layer.
        self.thought_graph = ThoughtGraph()
        self.memory_git = MemoryGit()
        self.skill_forge = SkillForge()
        self.reflection = ReflectionEngine(self.skill_forge, self.thought_graph)
        self.pipe_registry: PipeCommandRegistry = default_registry
        self._context_window_tokens = context_window_tokens

        self._current_session: EnhancedSession | None = None
        self._sessions: dict[str, EnhancedSession] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def create_session(self, title: str = "New Chat") -> EnhancedSession:
        """Create a new session with fresh graph and context map."""
        from .utils.helpers import generate_id

        session = EnhancedSession(
            id=generate_id(),
            title=title,
            context_map=ContextMap(max_tokens=self._context_window_tokens),
        )
        self._sessions[session.id] = session
        self._current_session = session

        # Seed context map with SOUL and tool definitions.
        cm = session.context_map
        if cm:
            cm.add(
                source=ContextSource.SYSTEM,
                label="System instructions",
                content=self.prompt.build_system_prompt() if hasattr(self.prompt, 'build_system_prompt') else "",
                pinned=True,
                priority=100,
            )
        self.thought_graph.clear()
        return session

    @property
    def current_session(self) -> EnhancedSession | None:
        return self._current_session

    # ------------------------------------------------------------------
    # Pipe command handling
    # ------------------------------------------------------------------
    def _try_pipe_command(self, text: str) -> str | None:
        """Check if text is a pipe command and execute it.

        Returns:
            Command output if it was a command, None otherwise.
        """
        if not self.pipe_registry.is_command(text.strip()) and not self.pipe_registry.is_pipeline(text.strip()):
            return None
        ctx = PipeContext(
            agent=self,
            session_id=self._current_session.id if self._current_session else "",
            raw_input=text,
        )
        try:
            return self.pipe_registry.execute(text.strip(), ctx)
        except KeyError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            logger.exception("Pipe command error")
            return f"Command error: {exc}"

    # ------------------------------------------------------------------
    # Main chat loop
    # ------------------------------------------------------------------
    async def send_message(
        self,
        user_input: str,
        session: EnhancedSession | None = None,
    ) -> AsyncGenerator[str, None]:
        """Process user input with full innovation-layer instrumentation.

        1. Check for pipe commands first.
        2. Record the user input in the Thought Graph.
        3. Recall relevant memories (and commit to Memory Git).
        4. Match skills.
        5. Populate the Context Map.
        6. Run the LLM + tool loop, recording every step.
        7. Stream response text.
        8. Trigger reflection after task completion.
        """
        session = session or self._current_session
        if session is None:
            session = self.create_session()

        # Use the session's thought graph.
        graph = session.thought_graph
        graph.clear() if not graph.roots else None
        cm = session.context_map

        # --- 1. Pipe commands ---
        pipe_result = self._try_pipe_command(user_input)
        if pipe_result is not None:
            yield pipe_result
            return

        # --- 2. Record user input ---
        user_node = graph.add_node(
            NodeKind.USER_INPUT,
            label=f"User: {user_input[:60]}",
            detail=user_input,
        )
        session.messages.append(LLMMessage(role="user", content=user_input))
        if cm:
            cm.add(
                source=ContextSource.USER_MESSAGE,
                label=f"User message ({len(user_input)} chars)",
                content=user_input,
                priority=80,
            )

        # --- 3. Memory recall ---
        recalled_memories: list[str] = []
        if self.config.memory.enabled:
            recall_node = graph.add_node(
                NodeKind.MEMORY_RECALL,
                label=f"Recalling memories for: {user_input[:40]}",
                parent_id=user_node.id,
            )
            try:
                results = self.memory.search(user_input, limit=5) if hasattr(self.memory, 'search') else []
                for m in results:
                    content = m.content if hasattr(m, 'content') else str(m)
                    recalled_memories.append(content)
                    graph.add_node(
                        NodeKind.MEMORY_RECALL,
                        label=f"Memory: {content[:50]}",
                        detail=content,
                        parent_id=recall_node.id,
                    )
                    if cm:
                        cm.add(
                            source=ContextSource.MEMORY_RECALL,
                            label=f"Memory: {content[:40]}",
                            content=content,
                            priority=40,
                        )
            except Exception as exc:
                graph.add_node(
                    NodeKind.ERROR,
                    label=f"Memory recall failed: {exc}",
                    parent_id=recall_node.id,
                )

        # --- 4. Skill matching ---
        matched_skills = []
        if hasattr(self.skills, 'match_skills'):
            try:
                matched = self.skills.match_skills(user_input)
                matched_skills = [s for s, _score in matched]
                for skill in matched_skills:
                    graph.add_node(
                        NodeKind.SKILL_MATCH,
                        label=f"Skill matched: {skill.name}",
                        detail=getattr(skill, 'description', ''),
                        parent_id=user_node.id,
                    )
                    if cm:
                        cm.add(
                            source=ContextSource.SKILL,
                            label=f"Skill: {skill.name}",
                            content=getattr(skill, 'content', getattr(skill, 'description', '')),
                            priority=70,
                        )
            except Exception as exc:
                logger.warning("Skill matching failed: %s", exc)

        # --- 5. Build messages via context map ---
        if cm:
            # Compress if needed before sending.
            if cm.compression_needed():
                evicted = cm.compress(reserve_tokens=500)
                for e in evicted:
                    graph.add_node(
                        NodeKind.COMPRESSION,
                        label=f"Evicted: {e.label[:40]}",
                        parent_id=user_node.id,
                        metadata={"reason": "token_budget", "tokens": e.estimated_tokens()},
                    )
            api_messages = cm.to_messages()
        else:
            api_messages = [m.to_dict() for m in session.messages]

        # --- 6. LLM + tool loop ---
        # Non-streaming chat so tool_calls are complete; UI still receives
        # full content chunks via the async generator.
        tool_defs = self.tools.get_definitions() if hasattr(self.tools, "get_definitions") else []
        full_response_parts: list[str] = []
        max_iterations = self.config.agent.max_tool_iterations

        for iteration in range(max_iterations + 1):
            think_node = graph.add_node(
                NodeKind.LLM_THINK,
                label=f"LLM thinking (iteration {iteration + 1})",
                parent_id=graph.active_node.id if graph.active_node else None,
            )

            llm_msgs = [
                LLMMessage(**m) if isinstance(m, dict) else m for m in api_messages
            ]
            response = await self.llm.chat(
                llm_msgs,
                tools=tool_defs if iteration == 0 else None,
                stream=False,
            )
            collected = [response.content] if response.content else []
            if response.content:
                yield response.content

            think_node.label = f"LLM response ({len(''.join(collected))} chars)"
            think_node.detail = "".join(collected)[:2000]
            full_response_parts.append("".join(collected))

            tool_calls = response.tool_calls
            if not tool_calls:
                break

            for tc in tool_calls:
                tc_name = (
                    tc.get("function", {}).get("name", tc.get("name", "unknown"))
                    if isinstance(tc, dict)
                    else getattr(tc, "name", "unknown")
                )
                tc_args = (
                    tc.get("function", {}).get("arguments", {})
                    if isinstance(tc, dict)
                    else getattr(tc, "arguments", {})
                )
                if isinstance(tc_args, str):
                    try:
                        import json as _json

                        tc_args = _json.loads(tc_args) if tc_args.strip() else {}
                    except Exception:
                        tc_args = {"_raw": tc_args}
                if not isinstance(tc_args, dict):
                    tc_args = {"value": tc_args}

                tool_node = graph.add_node(
                    NodeKind.TOOL_CALL,
                    label=f"Tool: {tc_name}",
                    detail=str(tc_args)[:500],
                    parent_id=think_node.id,
                )

                try:
                    result = await self.tools.execute(tc_name, **tc_args)
                    result_str = str(result)
                    graph.add_node(
                        NodeKind.TOOL_RESULT,
                        label=f"Result: {result_str[:50]}",
                        detail=result_str[:2000],
                        parent_id=tool_node.id,
                    )
                    api_messages.append(
                        {
                            "role": "assistant",
                            "content": response.content or "",
                            "tool_calls": [tc] if isinstance(tc, dict) else [],
                        }
                    )
                    api_messages.append(
                        {
                            "role": "tool",
                            "content": result_str,
                            "tool_call_id": tc.get("id", "") if isinstance(tc, dict) else "",
                        }
                    )
                except Exception as exc:
                    error_msg = f"Tool error: {exc}"
                    graph.add_node(
                        NodeKind.ERROR,
                        label=f"Tool {tc_name} failed: {exc}",
                        parent_id=tool_node.id,
                    )
                    api_messages.append({"role": "tool", "content": error_msg})

        # --- 7. Finalize response ---
        final_text = "".join(full_response_parts)
        session.messages.append(LLMMessage(role="assistant", content=final_text))

        if cm:
            cm.add(
                source=ContextSource.ASSISTANT_MESSAGE,
                label=f"Assistant response ({len(final_text)} chars)",
                content=final_text,
                priority=50,
            )

        # --- 8. Memory extraction + Git commit ---
        if self.config.memory.enabled and hasattr(self.memory, 'extract_and_store'):
            try:
                old_state = dict(self.memory_git.state)
                self.memory.extract_and_store(session.messages[-2:])
                # Commit any new memories.
                new_diffs = []
                # Simple heuristic: if there are new memories, commit.
                if hasattr(self.memory, 'get_recent'):
                    recent = self.memory.get_recent(limit=3)
                    for m in recent:
                        content = m.content if hasattr(m, 'content') else str(m)
                        key = m.id if hasattr(m, 'id') else content[:30]
                        if key not in old_state:
                            new_diffs.append(
                                MemoryDiff("add", key, new_value=content, layer="episodic")
                            )
                if new_diffs:
                    commit = self.memory_git.commit(
                        f"Memory extraction from: {user_input[:50]}",
                        new_diffs,
                    )
                    graph.add_node(
                        NodeKind.MEMORY_STORE,
                        label=f"Memory commit: {commit.hash[:8]}",
                        detail=commit.summary(),
                        parent_id=user_node.id,
                    )
            except Exception as exc:
                logger.warning("Memory extraction failed: %s", exc)

        # --- 9. Async reflection (non-blocking) ---
        # In a real implementation, this would be scheduled as a background task.
        # For now, we record that reflection should happen.
        graph.add_node(
            NodeKind.REFLECTION,
            label="Reflection scheduled",
            detail="Use /reflect to trigger post-task analysis",
            parent_id=graph.active_node.id if graph.active_node else None,
            collapsed=True,
        )

    # ------------------------------------------------------------------
    # Explicit reflection trigger
    # ------------------------------------------------------------------
    async def reflect_now(self) -> str:
        """Run reflection on the most recent exchange.

        Returns:
            Human-readable reflection summary.
        """
        if not self._current_session or not self._current_session.messages:
            return "No conversation to reflect on."

        msgs = self._current_session.messages
        user_msgs = [m for m in msgs if m.role == "user"]
        assistant_msgs = [m for m in msgs if m.role == "assistant"]

        if not user_msgs:
            return "No user messages to reflect on."

        last_user = user_msgs[-1].content
        last_assistant = assistant_msgs[-1].content if assistant_msgs else ""

        outcome = TaskOutcome(
            description=last_user[:200],
            success=True,
            tools_used=list(self.tools.list_names()) if hasattr(self.tools, 'list_names') else [],
            conversation_excerpt=f"User: {last_user}\n\nAssistant: {last_assistant[:1000]}",
        )

        # Get existing skills for context.
        existing_skills = []
        if hasattr(self.skills, 'list_skills'):
            for s in self.skills.list_skills():
                existing_skills.append({
                    "name": s.name,
                    "description": getattr(s, 'description', ''),
                })

        result = await self.reflection.reflect(outcome, existing_skills)

        lines = [
            "## Reflection Complete",
            "",
            result.self_assessment,
            "",
            f"**Confidence:** {result.confidence:.2f}",
            f"**Insights:** {len(result.insights)}",
            f"**Proposed changes:** {len(result.proposed_skill_changes)}",
            "",
        ]

        for i in result.insights:
            lines.append(f"- [{i.category}] {i.description} (conf: {i.confidence:.2f})")

        pending = self.skill_forge.pending_reviews()
        if pending:
            lines.append("")
            lines.append(f"🔨 {len(pending)} skill proposal(s) awaiting review.")
            lines.append("Use `/forge list` to view them.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    async def chat(self, user_input: str) -> str:
        """Non-streaming chat."""
        parts: list[str] = []
        async for chunk in self.send_message(user_input):
            parts.append(chunk)
        return "".join(parts)
