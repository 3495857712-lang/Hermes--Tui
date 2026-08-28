"""
Skill Forge View — review and merge self-evolution proposals.

Displays the proposal queue, shows diffs, accepts/rejects proposals,
and renders the reflection insights that motivated each change.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from ..skill_forge import ProposalStatus, SkillForge, SkillProposal

STATUS_ICONS = {
    ProposalStatus.DRAFT: "📝",
    ProposalStatus.PROPOSED: "🔔",
    ProposalStatus.REVIEWING: "👀",
    ProposalStatus.ACCEPTED: "✅",
    ProposalStatus.REJECTED: "❌",
    ProposalStatus.MERGED: "🎉",
    ProposalStatus.SUPERSEDED: "🔄",
}

TYPE_ICONS = {
    "new_skill": "✨",
    "modify_skill": "📝",
    "delete_skill": "🗑",
    "add_reference": "📄",
    "add_script": "🔧",
    "improve_description": "🎯",
}


class SkillForgeView(VerticalScroll):
    """Panel for the Skill Forge proposal queue and review."""

    DEFAULT_CSS = """
    SkillForgeView {
        background: $surface;
        color: $text;
        padding: 1 2;
        width: 1fr;
    }

    .sf-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    .sf-proposal {
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    .sf-proposal.selected {
        border: double $accent;
    }

    .sf-status {
        text-style: bold;
    }

    .sf-diff {
        background: $boost;
        color: $text-muted;
        padding: 1;
        margin-top: 1;
    }

    .sf-add {
        color: $success;
    }

    .sf-del {
        color: $error;
    }

    .sf-insight {
        color: $text-muted;
        margin-left: 2;
    }

    .sf-empty {
        color: $text-muted;
        text-style: italic;
    }
    """

    selected_index: reactive[int] = reactive(0)
    filter_status: reactive[ProposalStatus | None] = reactive(None)

    def __init__(self, forge: SkillForge, **kwargs) -> None:
        super().__init__(**kwargs)
        self._forge = forge
        self._visible: list[str] = []

    def on_mount(self) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        """Re-render the proposal queue."""
        self.remove_children()
        self.mount(Static("[sf-title]🔨 Skill Forge[/]"))

        proposals = self._forge.list_proposals(status=self.filter_status)
        self._visible = [p.id for p in proposals]

        if not proposals:
            self.mount(
                Static(
                    "[sf-empty]  No proposals. The agent will propose skill "
                    "improvements after completing tasks.[/]"
                )
            )
            return

        # Summary.
        pending = len(self._forge.pending_reviews())
        merged = len(self._forge.list_proposals(status=ProposalStatus.MERGED))
        self.mount(
            Static(
                f"  {len(proposals)} proposals shown | "
                f"[sf-status]{pending} pending[/] | "
                f"{merged} merged"
            )
        )
        self.mount(Static(""))

        for i, p in enumerate(proposals):
            is_selected = i == self.selected_index
            self._render_proposal(p, is_selected)

    def _render_proposal(self, p: SkillProposal, selected: bool) -> None:
        """Render a single proposal card."""
        sel_class = " selected" if selected else ""
        status_icon = STATUS_ICONS.get(p.status, "?")
        type_icon = TYPE_ICONS.get(p.proposal_type.value, "❓")

        # Header.
        self.mount(
            Static(
                f"[sf-proposal{sel_class}]"
                f"{type_icon} {status_icon} [sf-status]{p.id}[/] — {p.title}\n"
                f"  Type: {p.proposal_type.value} | "
                f"Status: {p.status.value} | "
                f"Target: {p.target_skill or '(new)'}\n"
                f"  {p.description[:200]}"
                f"[/]"
            )
        )

        # Insights.
        if p.insights:
            self.mount(Static("  [sf-status]Insights:[/]"))
            for insight in p.insights[:3]:
                self.mount(
                    Static(
                        f"  [sf-insight]• [{insight.category}] "
                        f"{insight.description[:100]} "
                        f"(conf: {insight.confidence:.2f})[/]"
                    )
                )

        # Diff (only for selected proposal).
        if selected and p.diffs:
            self.mount(Static("  [sf-status]Diff:[/]"))
            for d in p.diffs:
                for line in d.old_lines:
                    self.mount(Static(f"  [sf-diff][sf-del]- {line}[/][/]"))
                for line in d.new_lines:
                    self.mount(Static(f"  [sf-diff][sf-add]+ {line}[/][/]"))

        # Review comments.
        if p.review_comments:
            self.mount(Static("  [sf-status]Comments:[/]"))
            for c in p.review_comments[-3:]:
                self.mount(
                    Static(f"  [sf-insight]{c.get('author', '?')}: {c.get('body', '')[:100]}[/]")
                )

    def move_selection(self, delta: int) -> None:
        """Move selection cursor."""
        if not self._visible:
            return
        self.selected_index = max(0, min(len(self._visible) - 1, self.selected_index + delta))
        self.refresh_view()

    def accept_selected(self) -> str | None:
        """Accept the selected proposal. Returns ID or None."""
        if 0 <= self.selected_index < len(self._visible):
            pid = self._visible[self.selected_index]
            self._forge.accept(pid)
            self.refresh_view()
            return pid
        return None

    def reject_selected(self, reason: str = "Rejected by user") -> str | None:
        """Reject the selected proposal."""
        if 0 <= self.selected_index < len(self._visible):
            pid = self._visible[self.selected_index]
            self._forge.reject(pid, reason)
            self.refresh_view()
            return pid
        return None

    def merge_selected(self) -> str | None:
        """Merge the selected (must be accepted first)."""
        if 0 <= self.selected_index < len(self._visible):
            pid = self._visible[self.selected_index]
            try:
                self._forge.merge(pid)
                self.refresh_view()
                return pid
            except ValueError as exc:
                self.mount(Static(f"  ❌ {exc}"))
                return None
        return None

    def cycle_filter(self) -> None:
        """Cycle through status filters."""
        statuses: list[ProposalStatus | None] = [
            None,
            ProposalStatus.PROPOSED,
            ProposalStatus.ACCEPTED,
            ProposalStatus.MERGED,
            ProposalStatus.REJECTED,
        ]
        if self.filter_status not in statuses:
            self.filter_status = None
        else:
            idx = statuses.index(self.filter_status)
            self.filter_status = statuses[(idx + 1) % len(statuses)]
        self.selected_index = 0
        self.refresh_view()
