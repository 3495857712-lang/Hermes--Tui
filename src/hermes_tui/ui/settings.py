"""Settings screen for Hermes TUI.

Provides a simple form for editing configuration values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Switch

from hermes_tui.config import Config

if TYPE_CHECKING:
    from textual.app import ComposeResult


class SettingsScreen(ModalScreen[bool]):
    """Modal settings dialog.

    Args:
        config: Current configuration (copied, not mutated directly).
    """

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 70;
        height: auto;
        max-height: 40;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    .setting-row {
        height: 3;
        padding: 0 1;
    }

    .setting-label {
        width: 20;
        padding-top: 1;
    }

    .setting-input {
        width: 1fr;
    }

    #settings-buttons {
        padding-top: 1;
        align-horizontal: right;
    }

    Button {
        margin-left: 2;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, config: Config, **kwargs: object) -> None:
        """Initialize the settings screen.

        Args:
            config: The current configuration.
        """
        super().__init__(**kwargs)
        self._config = config

    def compose(self) -> ComposeResult:
        """Compose the settings form.

        Returns:
            Iterator of child widgets.
        """
        with Vertical(id="settings-container"):
            yield Static("[b]Settings[/b]", id="settings-title")
            yield Static("")

            with Horizontal(classes="setting-row"):
                yield Label("Model", classes="setting-label")
                yield Input(
                    value=self._config.llm.model,
                    id="setting-model",
                    classes="setting-input",
                )

            with Horizontal(classes="setting-row"):
                yield Label("API Base URL", classes="setting-label")
                yield Input(
                    value=self._config.llm.base_url,
                    id="setting-base-url",
                    classes="setting-input",
                )

            with Horizontal(classes="setting-row"):
                yield Label("API Key", classes="setting-label")
                yield Input(
                    value=self._config.llm.api_key,
                    id="setting-api-key",
                    password=True,
                    classes="setting-input",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Temperature", classes="setting-label")
                yield Input(
                    value=str(self._config.llm.temperature),
                    id="setting-temperature",
                    classes="setting-input",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Max Tokens", classes="setting-label")
                yield Input(
                    value=str(self._config.llm.max_tokens),
                    id="setting-max-tokens",
                    classes="setting-input",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Dark Theme", classes="setting-label")
                yield Switch(
                    value=self._config.ui.theme == "dark",
                    id="setting-dark-theme",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Animations", classes="setting-label")
                yield Switch(
                    value=self._config.ui.animation,
                    id="setting-animation",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Memory", classes="setting-label")
                yield Switch(
                    value=self._config.memory.enabled,
                    id="setting-memory",
                )

            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="success", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button event.
        """
        if event.button.id == "btn-save":
            self._save_settings()
            self.dismiss(True)
        elif event.button.id == "btn-cancel":
            self.dismiss(False)

    def action_cancel(self) -> None:
        """Handle the cancel action."""
        self.dismiss(False)

    def _save_settings(self) -> None:
        """Read form values and update config."""
        self._config.llm.model = self.query_one("#setting-model", Input).value
        self._config.llm.base_url = self.query_one("#setting-base-url", Input).value
        self._config.llm.api_key = self.query_one("#setting-api-key", Input).value

        try:
            self._config.llm.temperature = float(
                self.query_one("#setting-temperature", Input).value
            )
        except ValueError:
            pass

        try:
            self._config.llm.max_tokens = int(
                self.query_one("#setting-max-tokens", Input).value
            )
        except ValueError:
            pass

        self._config.ui.theme = (
            "dark" if self.query_one("#setting-dark-theme", Switch).value else "light"
        )
        self._config.ui.animation = self.query_one("#setting-animation", Switch).value
        self._config.memory.enabled = self.query_one("#setting-memory", Switch).value

        try:
            self._config.save_yaml()
        except OSError:
            pass
