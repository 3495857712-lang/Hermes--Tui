"""Tests for Pipe Commands module."""

from __future__ import annotations

import pytest

from hermes_tui.pipe_commands import PipeCommandRegistry, PipeContext, default_registry


@pytest.fixture()
def registry() -> PipeCommandRegistry:
    return PipeCommandRegistry().builtin()


class TestParsing:
    def test_single_command(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse("/help")
        assert stages == [("help", "")]

    def test_command_with_args(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse("/recall python errors")
        assert stages == [("recall", "python errors")]

    def test_pipeline_two_stages(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse("/recall python | /summarize")
        assert len(stages) == 2
        assert stages[0] == ("recall", "python")
        assert stages[1] == ("summarize", "")

    def test_pipeline_three_stages(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse("/history last 5 | /reflect | /forge propose")
        assert len(stages) == 3
        assert stages[0] == ("history", "last 5")
        assert stages[1] == ("reflect", "")
        assert stages[2] == ("forge", "propose")

    def test_quoted_args_not_split(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse('/recall "python | error" | /summarize')
        assert len(stages) == 2
        assert "python | error" in stages[0][1]

    def test_empty_input(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse("")
        assert stages == []

    def test_non_command_ignored(self, registry: PipeCommandRegistry) -> None:
        stages = registry.parse("hello world")
        assert stages == []


class TestCommandDetection:
    def test_is_command(self, registry: PipeCommandRegistry) -> None:
        assert registry.is_command("/help") is True
        assert registry.is_command("/recall test") is True

    def test_is_not_command(self, registry: PipeCommandRegistry) -> None:
        assert registry.is_command("hello") is False
        assert registry.is_command("no slash") is False

    def test_unknown_command(self, registry: PipeCommandRegistry) -> None:
        assert registry.is_command("/nonexistent") is False

    def test_is_pipeline(self, registry: PipeCommandRegistry) -> None:
        assert registry.is_pipeline("/a | /b") is True

    def test_is_not_pipeline(self, registry: PipeCommandRegistry) -> None:
        assert registry.is_pipeline("/help") is False
        assert registry.is_pipeline("hello") is False


class TestExecution:
    def test_help_command(self, registry: PipeCommandRegistry) -> None:
        result = registry.execute("/help")
        assert "Available Commands" in result
        assert "recall" in result
        assert "summarize" in result

    def test_help_specific_command(self, registry: PipeCommandRegistry) -> None:
        result = registry.execute("/help recall")
        assert "recall" in result
        assert "Search long-term memory" in result

    def test_grep_filters_lines(self, registry: PipeCommandRegistry) -> None:
        ctx = PipeContext(raw_input="error in line one\nsuccess line two\nERROR in three")
        # /grep reads from ctx.args for pattern, and text is piped.
        # First stage gets raw_input.
        result = registry.execute("/grep error", ctx)
        lines = result.strip().splitlines()
        assert len(lines) == 2
        assert all("error" in line.lower() for line in lines)

    def test_grep_invalid_regex(self, registry: PipeCommandRegistry) -> None:
        ctx = PipeContext(raw_input="test line")
        result = registry.execute("/grep [invalid", ctx)
        assert "invalid regex" in result.lower()

    def test_summarize_fallback(self, registry: PipeCommandRegistry) -> None:
        text = "line one\nline two\nline three\nline four\nline five"
        ctx = PipeContext(raw_input=text)
        result = registry.execute("/summarize 2", ctx)
        assert "line one" in result
        assert "line two" in result
        assert "line three" not in result

    def test_unknown_command_raises(self, registry: PipeCommandRegistry) -> None:
        with pytest.raises(KeyError, match="Unknown command"):
            registry.execute("/nonexistent")

    def test_history_no_session(self, registry: PipeCommandRegistry) -> None:
        result = registry.execute("/history")
        assert "no active session" in result.lower()

    def test_model_show_no_agent(self, registry: PipeCommandRegistry) -> None:
        result = registry.execute("/model show")
        assert "no agent" in result.lower()

    def test_skill_list_no_agent(self, registry: PipeCommandRegistry) -> None:
        result = registry.execute("/skill list")
        # Should not crash, may show no agent message.


class TestCustomCommands:
    def test_register_custom_command(self) -> None:
        reg = PipeCommandRegistry()

        @reg.register("hello", description="Say hello")
        def _hello(text: str, ctx: PipeContext) -> str:
            return f"Hello, {ctx.args}!"

        result = reg.execute("/hello World")
        assert result == "Hello, World!"

    def test_custom_command_in_help(self) -> None:
        reg = PipeCommandRegistry()

        @reg.register("mycmd", description="My custom command", category="custom")
        def _mycmd(text: str, ctx: PipeContext) -> str:
            return text

        result = reg.execute("/help")
        assert "mycmd" in result
        assert "custom" in result.lower()

    def test_pipeline_with_custom(self) -> None:
        reg = PipeCommandRegistry()

        @reg.register("upper")
        def _upper(text: str, ctx: PipeContext) -> str:
            return text.upper()

        @reg.register("first")
        def _first(text: str, ctx: PipeContext) -> str:
            return text.splitlines()[0] if text else ""

        ctx = PipeContext(raw_input="hello world\nsecond line")
        result = reg.execute("/first | /upper", ctx)
        assert result == "HELLO WORLD"


class TestCategories:
    def test_categories_exist(self, registry: PipeCommandRegistry) -> None:
        cats = registry.categories()
        assert "memory" in cats
        assert "text" in cats
        assert "context" in cats
        assert "forge" in cats

    def test_list_by_category(self, registry: PipeCommandRegistry) -> None:
        memory_cmds = registry.list_commands(category="memory")
        assert any(c.name == "recall" for c in memory_cmds)
        text_cmds = registry.list_commands(category="text")
        assert any(c.name == "grep" for c in text_cmds)


class TestDefaultRegistry:
    def test_default_registry_has_commands(self) -> None:
        assert len(default_registry.list_commands()) >= 8

    def test_default_registry_has_recall(self) -> None:
        assert default_registry.get("recall") is not None
