"""
Pipe Commands — Unix-style composable slash commands.

Instead of a flat list of isolated slash commands, Hermes TUI supports
pipelines where the output of one command feeds into the next::

    /recall python errors | /summarize | /skill create
    /context show | /grep tool | /compact
    /history last 5 | /reflect | /forge propose

Each command is a pure-ish function: it receives a :class:`PipeContext`
and the current text, and returns transformed text.  This makes commands
composable, testable, and surprisingly powerful — it brings the Unix
philosophy to the agent's own introspection tools.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class PipeContext:
    """Runtime context passed through every stage of a pipeline.

    Attributes:
        agent: Reference to the active AIAgent (for memory, skills, etc.).
        session_id: Current session identifier.
        args: Raw argument string for the first command.
        variables: User/agent variables that persist across stages.
        raw_input: The original user input before any processing.
    """

    agent: Any = None
    session_id: str = ""
    args: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    raw_input: str = ""


class CommandHandler(Protocol):
    """Protocol for pipe command handlers."""

    def __call__(self, text: str, ctx: PipeContext) -> str: ...


@dataclass
class CommandSpec:
    """Specification for a registered pipe command.

    Attributes:
        name: Command name (without slash).
        handler: Function that transforms input text.
        description: One-line help text.
        usage: Argument syntax for help display.
        category: Grouping for help organisation.
        examples: Usage examples.
    """

    name: str
    handler: CommandHandler
    description: str = ""
    usage: str = ""
    category: str = "general"
    examples: list[str] = field(default_factory=list)


class PipeCommandRegistry:
    """Registry and executor for composable slash-command pipelines.

    Usage::

        registry = PipeCommandRegistry()
        registry.builtin()  # register defaults

        result = registry.execute("/recall python | /summarize", ctx)
    """

    def __init__(self) -> None:
        self._commands: dict[str, CommandSpec] = {}
        # Always register /help so it works even without calling .builtin().
        self._register_help()

    def _register_help(self) -> None:
        """Register the /help command (always available)."""
        if "help" in self._commands:
            return

        def _help(text: str, ctx: PipeContext) -> str:
            target = ctx.args.strip()
            if target:
                spec = self._commands.get(target)
                if not spec:
                    return f"Unknown command: /{target}"
                lines = [
                    f"/{spec.name} — {spec.description}",
                    f"  Usage: {spec.usage}",
                ]
                if spec.examples:
                    lines.append("  Examples:")
                    for ex in spec.examples:
                        lines.append(f"    {ex}")
                return "\n".join(lines)

            lines = ["## Available Commands", ""]
            for cat in self.categories():
                lines.append(f"### {cat}")
                for spec in self.list_commands(cat):
                    lines.append(f"  /{spec.name:12s} {spec.description}")
                lines.append("")
            lines.append("Chain commands with | : /recall python | /grep error")
            return "\n".join(lines)

        self._commands["help"] = CommandSpec(
            name="help",
            handler=_help,
            description="Show available commands",
            usage="/help [command]",
            category="general",
        )

    def register(
        self,
        name: str,
        description: str = "",
        usage: str = "",
        category: str = "general",
        examples: list[str] | None = None,
    ) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a pipe command.

        Args:
            name: Command name (without slash).
            description: One-line help.
            usage: Argument syntax.
            category: Help grouping.
            examples: Example invocations.

        Returns:
            Decorator that registers the function and returns it.
        """

        def decorator(fn: CommandHandler) -> CommandHandler:
            self._commands[name] = CommandSpec(
                name=name,
                handler=fn,
                description=description,
                usage=usage,
                category=category,
                examples=examples or [],
            )
            return fn

        return decorator

    def get(self, name: str) -> CommandSpec | None:
        """Look up a command by name."""
        return self._commands.get(name)

    def list_commands(self, category: str | None = None) -> list[CommandSpec]:
        """List all registered commands, optionally filtered by category."""
        cmds = list(self._commands.values())
        if category:
            cmds = [c for c in cmds if c.category == category]
        return sorted(cmds, key=lambda c: c.name)

    def categories(self) -> list[str]:
        """Return all command categories."""
        return sorted({c.category for c in self._commands.values()})

    # ------------------------------------------------------------------
    # Pipeline parsing
    # ------------------------------------------------------------------
    def parse(self, line: str) -> list[tuple[str, str]]:
        """Parse a pipeline string into (command, args) tuples.

        Args:
            line: Raw input like ``/recall python | /summarize``.

        Returns:
            List of (command_name, args_string) tuples.
        """
        # Split on | that are not inside quotes.
        segments: list[str] = []
        current = ""
        in_quote: str | None = None
        for char in line:
            if char in ('"', "'") and in_quote is None:
                in_quote = char
                current += char
            elif char == in_quote:
                in_quote = None
                current += char
            elif char == "|" and in_quote is None:
                segments.append(current.strip())
                current = ""
            else:
                current += char
        if current.strip():
            segments.append(current.strip())

        result: list[tuple[str, str]] = []
        for seg in segments:
            if not seg.startswith("/"):
                continue
            # Split command name from args.
            parts = seg[1:].split(None, 1)
            cmd_name = parts[0]
            cmd_args = parts[1] if len(parts) > 1 else ""
            result.append((cmd_name, cmd_args))
        return result

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(self, line: str, ctx: PipeContext | None = None) -> str:
        """Execute a pipeline string.

        Args:
            line: Raw pipeline input.
            ctx: Runtime context. A fresh one is created if None.

        Returns:
            Final output after all stages.

        Raises:
            KeyError: If a command in the pipeline is not registered.
        """
        ctx = ctx or PipeContext()
        stages = self.parse(line)
        if not stages:
            return line

        # First command gets the raw input as text.
        first_cmd, first_args = stages[0]
        ctx.args = first_args
        text = ctx.raw_input or ""

        for i, (cmd_name, cmd_args) in enumerate(stages):
            spec = self._commands.get(cmd_name)
            if spec is None:
                raise KeyError(f"Unknown command: /{cmd_name}")
            if i > 0:
                ctx.args = cmd_args
            logger.debug("Pipe stage %d: /%s %s", i, cmd_name, cmd_args[:40])
            text = spec.handler(text, ctx)

        return text

    def is_pipeline(self, text: str) -> bool:
        """Return True if text looks like a slash-command pipeline."""
        return text.strip().startswith("/") and "|" in text

    def is_command(self, text: str) -> bool:
        """Return True if text starts with a known slash command."""
        stripped = text.strip()
        if not stripped.startswith("/"):
            return False
        first = stripped[1:].split(None, 1)[0]
        return first in self._commands

    # ------------------------------------------------------------------
    # Built-in commands
    # ------------------------------------------------------------------
    def builtin(self) -> PipeCommandRegistry:
        """Register all built-in pipe commands and return self."""

        @self.register(
            "recall",
            description="Search long-term memory for relevant entries",
            usage="/recall <query>",
            category="memory",
            examples=["/recall python errors", "/recall user preferences"],
        )
        def _recall(text: str, ctx: PipeContext) -> str:
            query = ctx.args.strip() or text.strip()
            if not query or ctx.agent is None:
                return text
            try:
                memories = ctx.agent.memory.search(query, limit=5)
                if not memories:
                    return f"(no memories found for: {query})"
                lines = [f"## Recalled memories for '{query}':"]
                for m in memories:
                    lines.append(f"- [{m.layer}] {m.content}")
                return "\n".join(lines)
            except Exception as exc:
                return f"[recall error: {exc}]"

        @self.register(
            "summarize",
            description="Summarize the input text to key points",
            usage="/summarize [max_points]",
            category="text",
            examples=["/summarize", "/summarize 3"],
        )
        def _summarize(text: str, ctx: PipeContext) -> str:
            if not text.strip():
                return text
            # If agent is available, use LLM; otherwise do extractive summary.
            if ctx.agent is not None:
                return f"[LLM summary would go here for {len(text)} chars]"
            # Fallback: take first N non-empty lines.
            try:
                max_points = int(ctx.args.strip())
            except ValueError:
                max_points = 3
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines[:max_points])

        @self.register(
            "grep",
            description="Filter lines matching a pattern",
            usage="/grep <pattern>",
            category="text",
            examples=["/grep error", "/grep TODO|FIXME"],
        )
        def _grep(text: str, ctx: PipeContext) -> str:
            pattern = ctx.args.strip()
            if not pattern:
                return text
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                return f"[invalid regex: {pattern}]"
            return "\n".join(line for line in text.splitlines() if regex.search(line))

        @self.register(
            "context",
            description="Show or manage the current context window",
            usage="/context <show|pin|unpin|clear>",
            category="context",
            examples=["/context show", "/context pin last 3"],
        )
        def _context(text: str, ctx: PipeContext) -> str:
            sub = ctx.args.strip().split()
            action = sub[0] if sub else "show"
            if action == "show" and ctx.agent:
                session = getattr(ctx.agent, "_current_session", None)
                if session:
                    msgs = session.messages
                    total = sum(len(m.content or "") for m in msgs)
                    lines = [
                        f"Context: {len(msgs)} messages, ~{total} chars",
                        "---",
                    ]
                    for i, m in enumerate(msgs[-10:]):
                        label = m.role.upper()
                        preview = (m.content or "")[:60].replace("\n", " ")
                        lines.append(f"  [{i}] {label}: {preview}")
                    return "\n".join(lines)
            return f"/context {action}: (not yet implemented)"

        @self.register(
            "compact",
            description="Compress conversation history to save tokens",
            usage="/compact",
            category="context",
        )
        def _compact(text: str, ctx: PipeContext) -> str:
            return "[Context compression triggered]"

        @self.register(
            "reflect",
            description="Reflect on recent task and extract insights",
            usage="/reflect",
            category="forge",
            examples=["/history last 3 | /reflect"],
        )
        def _reflect(text: str, ctx: PipeContext) -> str:
            if ctx.agent is None:
                return text
            return (
                f"## Reflection\n\n"
                f"Input length: {len(text)} chars\n"
                f"[LLM reflection would analyze the task and produce insights]"
            )

        @self.register(
            "forge",
            description="Create or manage skill proposals",
            usage="/forge <propose|list|show|accept|reject>",
            category="forge",
            examples=["/forge propose", "/forge list", "/forge accept SP-0001"],
        )
        def _forge(text: str, ctx: PipeContext) -> str:
            sub = ctx.args.strip().split(None, 1)
            action = sub[0] if sub else "list"
            forge = getattr(ctx.agent, "skill_forge", None) if ctx.agent else None
            if action == "list" and forge:
                return str(forge.render_queue())
            if action == "propose" and forge:
                proposal = forge.reflect_and_propose(
                    task_description=text[:200],
                    task_outcome="",
                    conversation_excerpt=text,
                )
                return f"Created draft proposal: {proposal.summary()}"
            return f"/forge {action}: (not yet implemented or no forge available)"

        @self.register(
            "history",
            description="Show recent conversation messages",
            usage="/history [last N]",
            category="context",
            examples=["/history", "/history last 5"],
        )
        def _history(text: str, ctx: PipeContext) -> str:
            args = ctx.args.strip()
            n = 10
            if args.startswith("last "):
                try:
                    n = int(args.split()[1])
                except (IndexError, ValueError):
                    pass
            if ctx.agent is None:
                return "(no active session)"
            session = getattr(ctx.agent, "_current_session", None)
            if not session:
                return "(no active session)"
            msgs = session.messages[-n:]
            lines = [f"## Last {len(msgs)} messages"]
            for m in msgs:
                preview = (m.content or "")[:100].replace("\n", " ")
                lines.append(f"**{m.role}**: {preview}")
            return "\n".join(lines)

        @self.register(
            "skill",
            description="Manage skills (list, show, create)",
            usage="/skill <list|show|create|enable|disable>",
            category="skills",
        )
        def _skill(text: str, ctx: PipeContext) -> str:
            sub = ctx.args.strip().split(None, 1)
            action = sub[0] if sub else "list"
            skills = getattr(ctx.agent, "skills", None) if ctx.agent else None
            if action == "list" and skills:
                loaded = skills.list_skills()
                if not loaded:
                    return "No skills loaded."
                return "\n".join(f"- {s.name}: {s.description[:80]}" for s in loaded)
            return f"/skill {action}: (not yet implemented)"

        @self.register(
            "model",
            description="Switch or show the current LLM model",
            usage="/model <name>|show",
            category="config",
        )
        def _model(text: str, ctx: PipeContext) -> str:
            args = ctx.args.strip()
            if not args or args == "show":
                if ctx.agent:
                    cfg = ctx.agent.config.llm
                    return f"Current: {cfg.model} @ {cfg.base_url}"
                return "(no agent)"
            return f"[Model switch to '{args}' would happen here]"

        # /help is already registered in __init__ via _register_help().
        return self


# Global default registry instance.
default_registry = PipeCommandRegistry().builtin()
