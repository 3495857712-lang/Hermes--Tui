"""Bottom status bar for Hermes TUI."""

from __future__ import annotations

from datetime import datetime

from textual.reactive import reactive
from textual.widgets import Static

from ..utils.helpers import format_timestamp


class StatusBar(Static):
    """Status bar showing connection, model, token usage, and time."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        layout: horizontal;
    }

    #status-left {
        width: 1fr;
        text-align: left;
    }

    #status-center {
        width: 1fr;
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    #status-right {
        width: 1fr;
        text-align: right;
    }
    """

    connected: reactive[bool] = reactive(False)
    model_name: reactive[str] = reactive("")
    prompt_tokens: reactive[int] = reactive(0)
    completion_tokens: reactive[int] = reactive(0)
    total_tokens: reactive[int] = reactive(0)
    current_time: reactive[str] = reactive("")

    def __init__(self, **kwargs) -> None:
        """Initialise the status bar."""
        super().__init__(**kwargs)
        self._left = Static(id="status-left")
        self._center = Static(id="status-center")
        self._right = Static(id="status-right")

    def compose(self):
        """Compose the three status sections."""
        yield self._left
        yield self._center
        yield self._right

    def on_mount(self) -> None:
        """Start the clock and render initial state."""
        self.current_time = format_timestamp(datetime.now())
        self.set_interval(1.0, self._tick)
        self._refresh_all()

    def _tick(self) -> None:
        self.current_time = format_timestamp(datetime.now())
        self._refresh_all()

    def _refresh_all(self) -> None:
        dot = "*" if self.connected else "o"
        status = "Connected" if self.connected else "Disconnected"
        color_class = "" if self.connected else " disconnected"
        self._left.update(
            f"[connection-dot{color_class}]{dot}[/] {status}"
        )
        self._center.update(self.model_name)
        self._right.update(
            f"up {self.prompt_tokens} "
            f"down {self.completion_tokens} "
            f"sum {self.total_tokens}  {self.current_time}"
        )

    # Reactive watchers
    def watch_connected(self, _old: bool, _new: bool) -> None:
        """Re-render when connection status changes."""
        self._refresh_all()

    def watch_model_name(self, _old: str, _new: str) -> None:
        """Re-render when model name changes."""
        self._refresh_all()

    def set_token_usage(
        self,
        prompt: int = 0,
        completion: int = 0,
        total: int = 0,
    ) -> None:
        """Update token counts displayed in the status bar."""
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total
        self._refresh_all()
