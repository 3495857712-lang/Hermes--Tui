"""Sidebar panel showing model info, skills, memory, and sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from ..memory import MemoryManager
from ..skills import SkillLoader

if TYPE_CHECKING:  # pragma: no cover
    Session = dict[str, Any]


class Sidebar(Vertical):
    """Right-hand sidebar with model, skills, memory, and session info."""

    DEFAULT_CSS = """
    Sidebar {
        width: 32;
        min-width: 20;
        background: $bg-light;
        padding: 1 1;
        border-left: solid $border;
        overflow-y: auto;
    }

    .sidebar-section {
        height: auto;
        margin: 0 0 1 0;
    }

    .sidebar-title {
        text-style: bold;
        color: $accent;
        height: 1;
        margin-bottom: 0;
    }

    .sidebar-item {
        color: $text-muted;
        height: auto;
        padding-left: 1;
    }

    .connection-dot {
        color: $success;
    }

    .connection-dot.disconnected {
        color: $error;
    }

    .collapsed {
        display: none;
    }
    """

    collapsed: reactive[bool] = reactive(False)
    connected: reactive[bool] = reactive(False)
    model_name: reactive[str] = reactive("model")
    provider: reactive[str] = reactive("openai")

    def __init__(
        self,
        skills: SkillLoader | None = None,
        memory: MemoryManager | None = None,
        **kwargs,
    ) -> None:
        """Initialise the sidebar.

        Args:
            skills: Skill loader for listing skills.
            memory: Memory manager for stats.
        """
        super().__init__(**kwargs)
        self._skills = skills
        self._memory = memory
        self._sessions: list[Session] = []

        self._connection = Static(classes="sidebar-section")
        self._model_info = Static(classes="sidebar-section")
        self._skills_section = Static(classes="sidebar-section")
        self._memory_section = Static(classes="sidebar-section")
        self._sessions_section = Static(classes="sidebar-section")

    def compose(self):
        """Yield the sidebar sub-sections."""
        yield self._connection
        yield self._model_info
        yield self._skills_section
        yield self._memory_section
        yield self._sessions_section

    def on_mount(self) -> None:
        """Render initial content."""
        self.refresh_content()

    def toggle_collapse(self) -> None:
        """Toggle the sidebar between collapsed and expanded."""
        self.collapsed = not self.collapsed
        if self.collapsed:
            for child in self.children:
                child.add_class("collapsed")
        else:
            for child in self.children:
                child.remove_class("collapsed")

    def set_connected(self, connected: bool) -> None:
        """Update connection status."""
        self.connected = connected
        self.refresh_content()

    def set_model(self, model_name: str, provider: str = "openai") -> None:
        """Update model information."""
        self.model_name = model_name
        self.provider = provider
        self.refresh_content()

    def set_sessions(self, sessions: list[Session]) -> None:
        """Update the session list."""
        self._sessions = sessions
        self.refresh_content()

    def refresh_content(self) -> None:
        """Re-render all sidebar sections."""
        dot = "*" if self.connected else "o"
        label = "Connected" if self.connected else "Disconnected"
        cls = "" if self.connected else " disconnected"
        self._connection.update(f"[sidebar-title]Status[/]\n[connection-dot{cls}]{dot}[/] {label}")

        self._model_info.update(
            f"[sidebar-title]Model[/]\n[sidebar-item]{self.provider} / {self.model_name}[/]"
        )

        # Skills
        if self._skills is not None:
            skills = self._skills.list_skills()
            if skills:
                lines = [f"[sidebar-item]- {s.name}: {s.description[:40]}[/]" for s in skills[:10]]
                self._skills_section.update("[sidebar-title]Skills[/]\n" + "\n".join(lines))
            else:
                self._skills_section.update(
                    "[sidebar-title]Skills[/]\n[sidebar-item]No skills loaded[/]"
                )

        # Memory
        if self._memory is not None:
            total = self._memory.count()
            working = self._memory.count("working")
            episodic = self._memory.count("episodic")
            procedural = self._memory.count("procedural")
            self._memory_section.update(
                f"[sidebar-title]Memory[/]\n"
                f"[sidebar-item]Total: {total}  "
                f"W:{working} E:{episodic} P:{procedural}[/]"
            )

        # Sessions
        if self._sessions:
            lines = [f"[sidebar-item]- {s.title[:28]}[/]" for s in self._sessions[:15]]
            self._sessions_section.update("[sidebar-title]Sessions[/]\n" + "\n".join(lines))
        else:
            self._sessions_section.update(
                "[sidebar-title]Sessions[/]\n[sidebar-item]No saved sessions[/]"
            )
