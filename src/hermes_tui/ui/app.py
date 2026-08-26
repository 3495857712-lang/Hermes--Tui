"""
Hermes TUI — main application with three-panel innovation layout.

Instead of the traditional single-pane chat, Hermes TUI defaults to a
three-panel workspace:

┌──────────────┬──────────────────────┬──────────────┐
│ Thought      │  Chat / Pipe I/O     │ Context Map  │
│ Graph        │                      │              │
│ (reasoning)  │  (conversation)      │ (token budget│
│              │                      │  & sources)  │
├──────────────┴──────────────────────┴──────────────┤
│ Memory Git log / Skill Forge queue (status bar)    │
└────────────────────────────────────────────────────┘

Key bindings:
- Ctrl+G: focus Thought Graph panel
- Ctrl+C: focus Chat
- Ctrl+M: focus Context Map
- Ctrl+F: toggle Skill Forge / Memory Git bottom panel
- Ctrl+P: command palette
- /: start a pipe command
"""

from __future__ import annotations

import logging

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input

from ..config import Config
from ..enhanced_agent import EnhancedAIAgent
from ..thought_graph import ThoughtGraph
from .chat import ChatView
from .context_map_view import ContextMapView
from .forge_view import SkillForgeView
from .memory_git_view import MemoryGitView
from .status_bar import StatusBar
from .theme import HERMES_CSS, HermesTheme
from .thought_graph_view import ThoughtGraphView

logger = logging.getLogger(__name__)

_LAYOUT_CSS = """
Screen {
    layout: vertical;
    background: $bg;
    color: $text;
}

#main-panels {
    height: 1fr;
}

#left-panel {
    width: 35%;
    min-width: 30;
    border-right: solid $border;
}

#center-panel {
    width: 1fr;
    min-width: 40;
}

#right-panel {
    width: 30%;
    min-width: 25;
    border-left: solid $border;
}

#bottom-panel {
    height: 30%;
    display: none;
    border-top: solid $border;
}

#bottom-panel.visible {
    display: block;
}

#input-area {
    height: auto;
    padding: 0 1;
    background: $surface;
    border-top: solid $border;
}

#chat-input {
    margin: 0;
    background: $bg-light;
    color: $text;
    border: round $border;
}

#chat-input:focus {
    border: round $accent;
}

ThoughtGraphView {
    display: block;
}

ContextMapView {
    display: block;
}

SkillForgeView, MemoryGitView {
    display: block;
}
"""


class HermesApp(App):
    """Main Textual application for Hermes TUI."""

    CSS = HermesTheme.DARK + HERMES_CSS + _LAYOUT_CSS

    BINDINGS = [
        Binding("ctrl+g", "focus_graph", "Thought Graph", show=False),
        Binding("ctrl+c", "focus_chat", "Chat", show=False),
        Binding("ctrl+m", "focus_context", "Context Map", show=False),
        Binding("ctrl+f", "toggle_bottom", "Forge/Memory", show=False),
        Binding("ctrl+p", "command_palette", "Commands", show=False),
        Binding("ctrl+r", "reflect", "Reflect", show=False),
        Binding("ctrl+d", "toggle_dark", "Dark/Light", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        config: Config | None = None,
        agent: EnhancedAIAgent | None = None,
        **kwargs,
    ) -> None:
        theme_name = config.ui.theme if config is not None else "dark"
        # Rebuild CSS with the requested theme variables before App init.
        type(self).CSS = HermesTheme.get(theme_name) + HERMES_CSS + _LAYOUT_CSS
        super().__init__(**kwargs)
        self._config = config
        self._agent = agent
        self._bottom_mode: str = "forge"  # "forge" or "memory"

    def compose(self) -> ComposeResult:
        """Compose the three-panel + bottom layout."""
        yield Header(show_clock=True)

        with Horizontal(id="main-panels"):
            with Vertical(id="left-panel"):
                yield ThoughtGraphView(
                    self._agent.thought_graph if self._agent else ThoughtGraph(),
                    id="thought-graph",
                )
            with Vertical(id="center-panel"):
                yield ChatView(id="chat-view")
            with Vertical(id="right-panel"):
                yield ContextMapView(id="context-map")

        with Vertical(id="bottom-panel"):
            if self._agent:
                yield SkillForgeView(self._agent.skill_forge, id="forge-view")
                yield MemoryGitView(self._agent.memory_git, id="memory-view")

        with Vertical(id="input-area"):
            yield Input(
                placeholder="Send a message, or / for commands (pipe with |)...",
                id="chat-input",
            )

        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        """Initialise after mounting."""
        if self._agent is not None:
            session = self._agent.current_session or self._agent.create_session()
            cm_view = self.query_one("#context-map", ContextMapView)
            if session.context_map:
                cm_view.bind_context_map(session.context_map)

            status = self.query_one(StatusBar)
            if self._config is not None:
                status.model_name = self._config.llm.model
            status.connected = True

        self.query_one("#chat-input", Input).focus()
        self.title = "Hermes TUI"
        self.sub_title = "self-evolving terminal agent"

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        if event.input.id != "chat-input":
            return
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        chat = self.query_one("#chat-view", ChatView)
        chat.add_message("user", text)

        if self._agent is None:
            chat.add_message("assistant", "Agent not initialised. Check your configuration.")
            return

        session = self._agent.current_session or self._agent.create_session()
        if session.context_map:
            try:
                cm_view = self.query_one("#context-map", ContextMapView)
                cm_view.bind_context_map(session.context_map)
            except Exception:
                logger.debug("Context map bind skipped", exc_info=True)

        chat.show_loading()
        try:
            chat.start_streaming("assistant")
            async for chunk in self._agent.send_message(text, session):
                chat.append_streaming_chunk(chunk)
            chat.end_streaming()
        except Exception as exc:
            chat.end_streaming()
            chat.add_message("system", f"Error: {exc}")
            logger.exception("Agent error")
        finally:
            chat.hide_loading()

        self._refresh_panels()

    def _refresh_panels(self) -> None:
        """Refresh all innovation-layer views."""
        try:
            self.query_one("#thought-graph", ThoughtGraphView).refresh_graph()
        except Exception:
            pass
        try:
            self.query_one("#context-map", ContextMapView).refresh_view()
        except Exception:
            pass
        if self._bottom_mode == "forge":
            try:
                self.query_one("#forge-view", SkillForgeView).refresh_view()
            except Exception:
                pass
        else:
            try:
                self.query_one("#memory-view", MemoryGitView).refresh_view()
            except Exception:
                pass

    def action_focus_graph(self) -> None:
        self.query_one("#thought-graph", ThoughtGraphView).focus()

    def action_focus_chat(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def action_focus_context(self) -> None:
        self.query_one("#context-map", ContextMapView).focus()

    def action_toggle_bottom(self) -> None:
        """Toggle the bottom panel between Forge and Memory views."""
        bottom = self.query_one("#bottom-panel")
        if not bottom.has_class("visible"):
            bottom.add_class("visible")
            if self._bottom_mode == "forge":
                self.query_one("#forge-view").display = True
                self.query_one("#memory-view").display = False
            else:
                self.query_one("#forge-view").display = False
                self.query_one("#memory-view").display = True
        else:
            if self._bottom_mode == "forge":
                self._bottom_mode = "memory"
                self.query_one("#forge-view").display = False
                self.query_one("#memory-view").display = True
            else:
                self._bottom_mode = "forge"
                self.query_one("#forge-view").display = True
                self.query_one("#memory-view").display = False
            bottom.remove_class("visible")
        self._refresh_panels()

    async def action_reflect(self) -> None:
        """Trigger reflection on the last exchange."""
        if self._agent:
            result = await self._agent.reflect_now()
            chat = self.query_one("#chat-view", ChatView)
            chat.add_message("system", result)
            self._refresh_panels()

    def action_command_palette(self) -> None:
        """Open the command palette."""
        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = "/"
        input_widget.focus()


# CLI / docs alias
HermesTUI = HermesApp
