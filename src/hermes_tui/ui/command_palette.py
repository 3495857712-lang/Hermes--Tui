"""Command palette overlay with fuzzy command filtering."""

from __future__ import annotations

from collections.abc import Callable

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Input, Static


class CommandItem(Static):
    """A single selectable command row."""

    DEFAULT_CSS = """
    CommandItem {
        height: 1;
        padding: 0 1;
        color: $text;
    }
    CommandItem.highlighted {
        background: $accent;
        color: $bg;
    }
    """

    def __init__(self, label: str, command_id: str, **kwargs) -> None:
        """Initialise a command item.

        Args:
            label: Human-readable command name.
            command_id: Unique command identifier.
        """
        super().__init__(label, **kwargs)
        self.label = label
        self.command_id = command_id
        self.highlighted = False

    def set_highlight(self, on: bool) -> None:
        """Set or clear the highlight state."""
        self.highlighted = on
        if on:
            self.add_class("highlighted")
        else:
            self.remove_class("highlighted")


class CommandPalette(Vertical):
    """Modal command palette with fuzzy search and keyboard navigation."""

    DEFAULT_CSS = """
    CommandPalette {
        width: 60;
        max-height: 20;
        background: $bg-light;
        border: thick $accent;
        padding: 1;
        align: center middle;
    }

    #command-input {
        margin-bottom: 1;
    }

    #command-list {
        height: auto;
        max-height: 15;
    }
    """

    visible_reactive: reactive[bool] = reactive(False)

    COMMANDS: dict[str, str] = {
        "new_session": "New session",
        "switch_model": "Switch model",
        "view_skills": "View skills",
        "search_memory": "Search memory",
        "toggle_theme": "Toggle theme",
        "toggle_sidebar": "Toggle sidebar",
        "help": "Help",
        "quit": "Quit",
    }

    def __init__(
        self,
        on_command: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        """Initialise the command palette.

        Args:
            on_command: Callback invoked with the command ID when selected.
        """
        super().__init__(**kwargs)
        self.on_command = on_command
        self._selected_index = 0
        self._filtered: list[str] = list(self.COMMANDS.keys())
        self._items: list[CommandItem] = []
        self._input = Input(
            placeholder="Type a command...", id="command-input"
        )
        self._list = Vertical(id="command-list")

    def compose(self):
        """Compose the input and command list."""
        yield self._input
        yield self._list

    def on_mount(self) -> None:
        """Render the initial command list."""
        self.visible = False
        self._render_list()

    def open(self) -> None:
        """Show the palette and focus the input."""
        self.visible = True
        self._filtered = list(self.COMMANDS.keys())
        self._selected_index = 0
        self._input.value = ""
        self._render_list()
        self._input.focus()

    def close(self) -> None:
        """Hide the palette."""
        self.visible = False
        chat_view = self.app.query_one("#chat-view")
        chat_view.focus()

    def _render_list(self) -> None:
        """Rebuild the visible command list based on current filter."""
        for item in self._items:
            item.remove()
        self._items.clear()

        for idx, cmd_id in enumerate(self._filtered):
            label = self.COMMANDS.get(cmd_id, cmd_id)
            item = CommandItem(label=label, command_id=cmd_id)
            if idx == self._selected_index:
                item.set_highlight(True)
            self._items.append(item)
            self._list.mount(item)

    def _filter(self, query: str) -> None:
        """Filter commands by a simple substring match.

        Args:
            query: The search text.
        """
        q = query.strip().lower()
        if not q:
            self._filtered = list(self.COMMANDS.keys())
        else:
            self._filtered = [
                cid
                for cid, label in self.COMMANDS.items()
                if q in label.lower()
            ]
        self._selected_index = 0
        self._render_list()

    def _move_selection(self, delta: int) -> None:
        if not self._filtered:
            return
        self._items[self._selected_index].set_highlight(False)
        self._selected_index = (self._selected_index + delta) % len(
            self._filtered
        )
        self._items[self._selected_index].set_highlight(True)

    def _execute_selected(self) -> None:
        if not self._filtered:
            return
        cmd_id = self._filtered[self._selected_index]
        self.close()
        if self.on_command is not None:
            self.on_command(cmd_id)

    # ---- Event handlers ----
    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-filter as the user types."""
        if event.input is self._input:
            self._filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Execute the highlighted command on Enter."""
        if event.input is self._input:
            self._execute_selected()

    def on_key(self, event) -> None:
        """Handle up/down/escape keys."""
        if not self.visible:
            return
        if event.key == "escape":
            self.close()
            event.stop()
        elif event.key == "up":
            self._move_selection(-1)
            event.stop()
        elif event.key == "down":
            self._move_selection(1)
            event.stop()
