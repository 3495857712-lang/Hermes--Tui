"""
Thought Graph View — renders the non-linear reasoning graph in TUI.

Instead of a flat chat log, this panel shows the agent's reasoning as
an expandable tree with ASCII connectors. Users can:
- Navigate with j/k or arrow keys
- Expand/collapse nodes with Enter
- See token counts per cognitive step
- Filter by node kind
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from ..thought_graph import NodeKind, ThoughtGraph, ThoughtNode

# ASCII art icons for each node kind.
KIND_ICONS = {
    NodeKind.USER_INPUT: "💬",
    NodeKind.LLM_THINK: "🧠",
    NodeKind.LLM_RESPONSE: "✨",
    NodeKind.TOOL_CALL: "🔧",
    NodeKind.TOOL_RESULT: "📤",
    NodeKind.MEMORY_RECALL: "🔍",
    NodeKind.MEMORY_STORE: "💾",
    NodeKind.SKILL_MATCH: "🎯",
    NodeKind.SKILL_LOAD: "📦",
    NodeKind.REFLECTION: "🪞",
    NodeKind.SKILL_PROPOSAL: "🔨",
    NodeKind.COMPRESSION: "🗜",
    NodeKind.ERROR: "❌",
    NodeKind.BRANCH: "🌿",
    NodeKind.MERGE: "🔀",
}

# Rich markup colours for node kinds.
KIND_COLORS = {
    NodeKind.USER_INPUT: "cyan",
    NodeKind.LLM_THINK: "bright_blue",
    NodeKind.LLM_RESPONSE: "green",
    NodeKind.TOOL_CALL: "yellow",
    NodeKind.TOOL_RESULT: "bright_yellow",
    NodeKind.MEMORY_RECALL: "magenta",
    NodeKind.MEMORY_STORE: "bright_magenta",
    NodeKind.SKILL_MATCH: "bright_cyan",
    NodeKind.SKILL_LOAD: "cyan",
    NodeKind.REFLECTION: "bright_white",
    NodeKind.SKILL_PROPOSAL: "bright_red",
    NodeKind.COMPRESSION: "grey50",
    NodeKind.ERROR: "red",
    NodeKind.BRANCH: "green",
    NodeKind.MERGE: "bright_green",
}


class ThoughtGraphView(VerticalScroll):
    """Panel that renders the :class:`ThoughtGraph` as an ASCII tree."""

    DEFAULT_CSS = """
    ThoughtGraphView {
        background: $surface;
        color: $text;
        padding: 1 2;
        border-right: solid $primary;
        width: 1fr;
        min-width: 40;
    }

    .tg-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .tg-node {
        height: auto;
        padding: 0 0;
    }

    .tg-node.selected {
        background: $accent;
        color: $surface;
    }

    .tg-detail {
        color: $text-muted;
        padding-left: 4;
        margin-left: 2;
        border-left: solid $primary;
    }

    .tg-stats {
        color: $text-muted;
        margin-top: 1;
        text-style: italic;
    }
    """

    selected_index: reactive[int] = reactive(0)
    filter_kind: reactive[NodeKind | None] = reactive(None)

    def __init__(self, graph: ThoughtGraph, **kwargs) -> None:
        super().__init__(**kwargs)
        self._graph = graph
        self._expanded: set[str] = set()
        self._visible_nodes: list[str] = []

    def on_mount(self) -> None:
        self._render_graph()

    def refresh_graph(self) -> None:
        """Re-render after the graph has been updated."""
        self._render_graph()

    def _render_graph(self) -> None:
        """Build the tree display."""
        lines_widgets: list[Static] = []

        # Title.
        lines_widgets.append(Static("[tg-title]🧠 Thought Graph[/]"))

        # Build visible node list.
        self._visible_nodes = []
        nodes = self._graph.walk()
        if self.filter_kind:
            nodes = [n for n in nodes if n.kind == self.filter_kind]

        if not nodes:
            lines_widgets.append(Static("  (no reasoning steps yet)"))
        else:
            for i, node in enumerate(nodes):
                self._visible_nodes.append(node.id)
                is_selected = i == self.selected_index
                widget = self._render_node(node, i, is_selected)
                lines_widgets.append(widget)

                # Show detail if expanded.
                if node.id in self._expanded and node.detail:
                    detail_text = node.detail[:500]
                    if len(node.detail) > 500:
                        detail_text += "..."
                    lines_widgets.append(Static(f"[tg-detail]{detail_text}[/]"))

        # Stats.
        stats = self._graph.stats()
        stats_text = (
            f"[tg-stats]{stats.total_nodes} nodes | "
            f"{stats.llm_calls} LLM | {stats.tool_calls} tools | "
            f"{stats.memories_recalled} recall | {stats.reflections} reflect | "
            f"{stats.total_tokens_in + stats.total_tokens_out:,} tok | "
            f"{stats.duration_ms:.0f}ms[/]"
        )
        lines_widgets.append(Static(stats_text))

        # Clear and re-mount.
        self.remove_children()
        for w in lines_widgets:
            self.mount(w)

    def _render_node(self, node: ThoughtNode, index: int, selected: bool) -> Static:
        """Render a single node line."""
        icon = KIND_ICONS.get(node.kind, "•")
        color = KIND_COLORS.get(node.kind, "white")
        label = node.label[:70]

        # Expand/collapse marker.
        has_children = len(node._children) > 0
        if has_children:
            marker = "▼" if node.id in self._expanded else "▶"
        else:
            marker = " "

        # Token info.
        tokens = node.metadata.get("tokens_in", 0) + node.metadata.get("tokens_out", 0)
        token_str = f" ({tokens:,}t)" if tokens else ""

        # Tags.
        tag_str = f" [{', '.join(node.tags)}]" if node.tags else ""

        # Selection highlight.
        sel_class = " selected" if selected else ""
        text = f"[tg-node{sel_class}]{marker} {icon} [{color}]{label}[/]{token_str}{tag_str}[/]"
        widget = Static(text)
        widget.thread_id = node.id  # type: ignore[attr-defined]
        return widget

    def toggle_selected(self) -> None:
        """Expand/collapse the currently selected node."""
        if 0 <= self.selected_index < len(self._visible_nodes):
            node_id = self._visible_nodes[self.selected_index]
            if node_id in self._expanded:
                self._expanded.discard(node_id)
            else:
                self._expanded.add(node_id)
            self._render_graph()

    def move_selection(self, delta: int) -> None:
        """Move the selection cursor up or down."""
        if not self._visible_nodes:
            return
        self.selected_index = max(0, min(len(self._visible_nodes) - 1, self.selected_index + delta))
        self._render_graph()

    def cycle_filter(self) -> None:
        """Cycle through node kind filters."""
        kinds = [None] + list(NodeKind)
        if self.filter_kind is None:
            self.filter_kind = NodeKind.LLM_THINK
        else:
            try:
                idx = kinds.index(self.filter_kind)
                self.filter_kind = kinds[(idx + 1) % len(kinds)]
            except ValueError:
                self.filter_kind = None
        self.selected_index = 0
        self._render_graph()

    def on_key(self, event) -> None:
        """Handle keyboard navigation."""
        if event.key == "j" or event.key == "down":
            self.move_selection(1)
            event.stop()
        elif event.key == "k" or event.key == "up":
            self.move_selection(-1)
            event.stop()
        elif event.key == "enter" or event.key == "space":
            self.toggle_selected()
            event.stop()
        elif event.key == "f":
            self.cycle_filter()
            event.stop()
