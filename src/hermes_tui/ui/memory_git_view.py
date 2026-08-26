"""
Memory Git View — version-controlled memory log and diff viewer.

Renders the Git-like commit history of memory mutations, supports
viewing diffs between commits, and shows branch information.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from ..memory_git import MemoryGit


class MemoryGitView(VerticalScroll):
    """Panel showing Memory Git commit log and diffs."""

    DEFAULT_CSS = """
    MemoryGitView {
        background: $surface;
        color: $text;
        padding: 1 2;
        width: 1fr;
    }

    .mg-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    .mg-branch {
        color: $accent;
    }

    .mg-commit {
        margin-bottom: 1;
    }

    .mg-hash {
        color: $text-muted;
    }

    .mg-add {
        color: $success;
    }

    .mg-del {
        color: $error;
    }

    .mg-mod {
        color: $warning;
    }

    .mg-msg {
        color: $text;
    }
    """

    show_diff_index: reactive[int] = reactive(-1)

    def __init__(self, memory_git: MemoryGit, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mg = memory_git

    def on_mount(self) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        """Re-render the commit log."""
        self.remove_children()
        self.mount(Static("[mg-title]💾 Memory Git[/]"))

        # Branch info.
        branches = self._mg.list_branches()
        branch_parts = []
        for name, _head, is_current in branches:
            marker = "●" if is_current else "○"
            branch_parts.append(f"[mg-branch]{marker} {name}[/]")
        self.mount(Static("  ".join(branch_parts)))
        self.mount(Static(""))

        # Commit log.
        commits = self._mg.log(limit=20)
        if not commits:
            self.mount(Static("  No commits yet."))
            return

        for i, c in enumerate(commits):
            adds = sum(1 for d in c.diffs if d.op == "add")
            mods = sum(1 for d in c.diffs if d.op == "modify")
            dels = sum(1 for d in c.diffs if d.op == "delete")

            stats = []
            if adds:
                stats.append(f"[mg-add]+{adds}[/]")
            if mods:
                stats.append(f"[mg-mod]~{mods}[/]")
            if dels:
                stats.append(f"[mg-del]-{dels}[/]")
            stats_str = " ".join(stats) if stats else "no changes"

            self.mount(
                Static(
                    f"[mg-commit]"
                    f"[mg-hash]{c.hash[:8]}[/] [mg-msg]{c.message}[/]  "
                    f"{stats_str}  ({c.author}, {c.branch})"
                    f"[/]"
                )
            )

            # Show diff if selected.
            if i == self.show_diff_index:
                for d in c.diffs:
                    if d.op == "add":
                        self.mount(Static(f"  [mg-add]+ {d.key}: {d.new_value}[/]"))
                    elif d.op == "delete":
                        self.mount(Static(f"  [mg-del]- {d.key}: {d.old_value}[/]"))
                    elif d.op == "modify":
                        self.mount(Static(f"  [mg-mod]~ {d.key}[/]"))
                        self.mount(Static(f"    [mg-del]- {d.old_value}[/]"))
                        self.mount(Static(f"    [mg-add]+ {d.new_value}[/]"))

        # Current state summary.
        state = self._mg.state
        self.mount(Static(""))
        self.mount(Static(f"[mg-title]Current state: {len(state)} memories[/]"))
        for key, value in list(state.items())[:10]:
            self.mount(Static(f"  {key}: {value[:60]}"))
        if len(state) > 10:
            self.mount(Static(f"  ... and {len(state) - 10} more"))

    def toggle_diff(self, index: int) -> None:
        """Toggle showing diff for a commit."""
        if self.show_diff_index == index:
            self.show_diff_index = -1
        else:
            self.show_diff_index = index
        self.refresh_view()
