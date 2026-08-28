"""Small reusable Textual widgets for Hermes TUI."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class LoadingDots(Static):
    """Animated three-dot loading indicator."""

    DEFAULT_CSS = """
    LoadingDots {
        width: auto;
        height: 1;
        color: $accent;
        text-style: bold;
    }
    """

    _frames = ["   ", ".  ", ".. ", "..."]
    _frame: reactive[int] = reactive(0)

    def on_mount(self) -> None:
        """Start the animation when the widget is mounted."""
        self.visible = False
        self.set_interval(0.3, self._advance)

    def _advance(self) -> None:
        if self.visible:
            self._frame = (self._frame + 1) % len(self._frames)
            self.update(self._frames[self._frame])

    def start(self) -> None:
        """Show and start the animation."""
        self.visible = True
        self._frame = 0
        self.update(self._frames[0])

    def stop(self) -> None:
        """Hide the animation."""
        self.visible = False
        self.update("")


class TokenCounter(Static):
    """Displays prompt/completion/total token usage."""

    DEFAULT_CSS = """
    TokenCounter {
        width: auto;
        height: 1;
        color: $text-muted;
    }
    """

    prompt_tokens: reactive[int] = reactive(0)
    completion_tokens: reactive[int] = reactive(0)
    total_tokens: reactive[int] = reactive(0)

    def _render_text(self) -> str:
        return f"up {self.prompt_tokens} down {self.completion_tokens} sum {self.total_tokens}"

    def watch_prompt_tokens(self, _old: int, _new: int) -> None:
        """Re-render when prompt tokens change."""
        self.update(self._render_text())

    def watch_completion_tokens(self, _old: int, _new: int) -> None:
        """Re-render when completion tokens change."""
        self.update(self._render_text())

    def watch_total_tokens(self, _old: int, _new: int) -> None:
        """Re-render when total tokens change."""
        self.update(self._render_text())

    def set_usage(
        self,
        prompt: int = 0,
        completion: int = 0,
        total: int = 0,
    ) -> None:
        """Update all token counts at once."""
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total


class ModelBadge(Static):
    """A small badge showing the active model name."""

    DEFAULT_CSS = """
    ModelBadge {
        width: auto;
        height: 1;
        color: $accent;
        text-style: bold;
    }
    """

    model_name: reactive[str] = reactive("model")

    def render(self) -> str:
        """Render the badge content."""
        return f"* {self.model_name}"

    def watch_model_name(self, _old: str, _new: str) -> None:
        """Refresh when the model name changes."""
        self.refresh()


class Divider(Static):
    """A simple horizontal divider line."""

    DEFAULT_CSS = """
    Divider {
        height: 1;
        color: $surface-lighten-1;
    }
    """

    def render(self) -> str:
        """Render a horizontal rule."""
        return "-" * self.size.width
