"""
Context Map View — visualise the LLM context window in real time.

Shows a live ASCII heat-map of token budget allocation by source,
pinned items, eviction history, and allows pin/unpin/clear operations.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from ..context_map import ContextMap, ContextSource

SOURCE_ICONS = {
    ContextSource.SYSTEM: "S",
    ContextSource.SOUL: "♥",
    ContextSource.USER_MESSAGE: "U",
    ContextSource.ASSISTANT_MESSAGE: "A",
    ContextSource.TOOL_RESULT: "T",
    ContextSource.SKILL: "K",
    ContextSource.MEMORY_RECALL: "M",
    ContextSource.MEMORY_SUMMARY: "m",
    ContextSource.TOOL_DEFINITION: "D",
    ContextSource.COMPRESSED_HISTORY: "C",
    ContextSource.PIPELINE_OUTPUT: "|",
    ContextSource.CUSTOM: "?",
}


class ContextMapView(VerticalScroll):
    """Panel that renders the :class:`ContextMap` as a live heat-map."""

    DEFAULT_CSS = """
    ContextMapView {
        background: $surface;
        color: $text;
        padding: 1 2;
        border-left: solid $secondary;
        width: 1fr;
        min-width: 30;
    }

    .cm-title {
        text-style: bold;
        color: $secondary;
        margin-bottom: 1;
    }

    .cm-bar {
        text-style: bold;
        margin-bottom: 1;
    }

    .cm-section {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .cm-item {
        color: $text;
    }

    .cm-item.pinned {
        color: $warning;
    }

    .cm-evicted {
        color: $error;
        text-style: strikethrough;
    }

    .cm-free {
        color: $success;
    }

    .cm-over {
        color: $error;
        text-style: bold;
    }
    """

    show_evicted: reactive[bool] = reactive(True)
    _context_map: ContextMap | None = None

    def bind_context_map(self, cm: ContextMap) -> None:
        """Attach a context map to this view."""
        self._context_map = cm
        self.refresh_view()

    def refresh_view(self) -> None:
        """Re-render the heat-map."""
        self.remove_children()
        self.mount(Static("[cm-title]🗺 Context Map[/]"))

        if self._context_map is None:
            self.mount(Static("  (no active context)"))
            return

        cm = self._context_map
        used = cm.used_tokens()
        total = cm.max_tokens
        free = cm.free_tokens()
        pct = (used / total * 100) if total else 0

        # Bar width.
        bar_width = 40
        filled = int(pct / 100 * bar_width)
        is_over = used > total

        if is_over:
            bar = "[cm-over]" + "█" * bar_width + "[/]"
        else:
            bar = "█" * filled + "░" * (bar_width - filled)

        status_class = "cm-over" if is_over else "cm-free"
        self.mount(
            Static(f"[cm-bar]{bar}[/]  [{status_class}]{used:,} / {total:,} tok ({pct:.1f}%)[/]")
        )

        if is_over:
            self.mount(Static("[cm-over]⚠ OVER BUDGET — compression needed[/]"))

        # Source breakdown.
        self.mount(Static("[cm-section]Source Breakdown[/]"))
        breakdown = cm.source_breakdown()
        if not breakdown:
            self.mount(Static("  (empty)"))
        for source, count, tokens in breakdown:
            icon = SOURCE_ICONS.get(source, "?")
            prop = tokens / total if total else 0
            mini_bar = "█" * int(prop * 20)
            has_pinned = any(i.pinned for i in cm.by_source(source))
            pin_mark = " ●" if has_pinned else ""
            self.mount(
                Static(
                    f"[cm-item]{icon} {source.value:<22} "
                    f"{count:>2}× {mini_bar} {tokens:>6,}t{pin_mark}[/]"
                )
            )

        # Free space.
        self.mount(Static(f"[cm-free]  Free: {free:,} tokens[/]"))

        # Pinned items.
        pinned = cm.pinned_items()
        if pinned:
            self.mount(Static("[cm-section]Pinned (never evicted)[/]"))
            for item in pinned:
                self.mount(Static(f"[cm-item pinned]  ● {item.label[:50]}[/]"))

        # Eviction log.
        if self.show_evicted:
            evicted = cm.eviction_log(8)
            if evicted:
                self.mount(Static("[cm-section]Evicted[/]"))
                for rec in evicted:
                    self.mount(
                        Static(
                            f"[cm-evicted]  ✕ {rec.label[:40]:40s} "
                            f"{rec.token_count:>6}t ({rec.reason.value})[/]"
                        )
                    )

        # Item list.
        items = cm.items()
        if items:
            self.mount(Static(f"[cm-section]Items ({len(items)})[/]"))
            for item in items[-15:]:
                pin = "●" if item.pinned else " "
                cls = "cm-item pinned" if item.pinned else "cm-item"
                self.mount(
                    Static(
                        f"[{cls}]  {pin} {item.id} [{item.source.value}] "
                        f"{item.estimated_tokens():>6}t  {item.label[:35]}[/]"
                    )
                )

    def toggle_evicted(self) -> None:
        """Toggle visibility of the eviction log."""
        self.show_evicted = not self.show_evicted
        self.refresh_view()
