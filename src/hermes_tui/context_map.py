"""
Context Map — visualise what's in the LLM's context window.

Most agent frameworks treat the context window as a black box: messages
go in, text comes out, and at some mysterious point old messages get
silently truncated.  The Context Map makes the context window a
first-class, inspectable object.

It tracks:
- Which messages/skills/memories are currently "in context"
- Token budget allocation per source
- What was compressed or evicted (and why)
- Pinned items that must never be evicted
- A live ASCII heat-map showing context density

This gives users and the agent itself visibility into *why* the model
remembers or forgets things — and the power to control it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ContextSource(str, Enum):
    """Where a context item came from."""

    SYSTEM = "system"
    SOUL = "soul"
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_RESULT = "tool_result"
    SKILL = "skill"
    MEMORY_RECALL = "memory_recall"
    MEMORY_SUMMARY = "memory_summary"
    TOOL_DEFINITION = "tool_definition"
    COMPRESSED_HISTORY = "compressed_history"
    PIPELINE_OUTPUT = "pipeline_output"
    CUSTOM = "custom"


class EvictionReason(str, Enum):
    """Why a context item was removed."""

    TOKEN_BUDGET = "token_budget"
    COMPRESSION = "compression"
    MANUAL = "manual"
    REPLACED = "replaced"
    SESSION_RESET = "session_reset"


@dataclass
class ContextItem:
    """A single piece of content currently in the context window.

    Attributes:
        id: Unique item ID.
        source: Where this item came from.
        label: Human-readable label.
        content: The actual text (may be large).
        token_count: Estimated token count.
        pinned: If True, this item is never evicted.
        priority: 0–100, higher = retained longer during compression.
        metadata: Additional structured data.
        visible: If False, present in context but hidden from map view.
    """

    id: str
    source: ContextSource
    label: str
    content: str = ""
    token_count: int = 0
    pinned: bool = False
    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)
    visible: bool = True

    def estimated_tokens(self) -> int:
        """Return stored token count or estimate from content length."""
        if self.token_count > 0:
            return self.token_count
        # Rough estimate: ~4 chars per token for English, ~2 for CJK.
        return max(1, len(self.content) // 4)


@dataclass
class EvictionRecord:
    """Record of a context item that was removed."""

    item_id: str
    label: str
    source: ContextSource
    reason: EvictionReason
    token_count: int
    timestamp_note: str = ""


class ContextMap:
    """Manages and visualises the LLM's context window.

    The map is token-budget aware: when items exceed the budget,
    lower-priority, unpinned items are evicted first (with a record
    kept for transparency).

    Usage::

        cm = ContextMap(max_tokens=8000)
        cm.add(ContextItem(...))
        cm.pin("system_prompt")
        print(cm.render_heatmap())
        cm.compress()  # evict low-priority items over budget
    """

    def __init__(self, max_tokens: int = 8000) -> None:
        self.max_tokens = max_tokens
        self._items: dict[str, ContextItem] = {}
        self._order: list[str] = []  # insertion/access order
        self._eviction_log: list[EvictionRecord] = []
        self._counter: int = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"ctx-{self._counter:04d}"

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def add(
        self,
        source: ContextSource,
        label: str,
        content: str,
        token_count: int = 0,
        pinned: bool = False,
        priority: int = 50,
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> ContextItem:
        """Add an item to the context map.

        Args:
            source: Origin of the content.
            label: Short label for display.
            content: Full text content.
            token_count: Pre-computed token count (0 to auto-estimate).
            pinned: Never evict this item.
            priority: Retention priority (0–100).
            item_id: Optional explicit ID.
            metadata: Extra structured data.
            visible: Show in heat-map.

        Returns:
            The created :class:`ContextItem`.
        """
        item_id = item_id or self._next_id()
        item = ContextItem(
            id=item_id,
            source=source,
            label=label,
            content=content,
            token_count=token_count,
            pinned=pinned,
            priority=max(0, min(100, priority)),
            metadata=metadata or {},
            visible=visible,
        )
        if item_id in self._items:
            # Replace existing item (same ID).
            self._eviction_log.append(
                EvictionRecord(
                    item_id=item_id,
                    label=self._items[item_id].label,
                    source=self._items[item_id].source,
                    reason=EvictionReason.REPLACED,
                    token_count=self._items[item_id].estimated_tokens(),
                )
            )
        else:
            self._order.append(item_id)
        self._items[item_id] = item
        logger.debug(
            "Context +%s [%s] %s (~%d tok)",
            item_id,
            source.value,
            label[:40],
            item.estimated_tokens(),
        )
        return item

    def remove(
        self, item_id: str, reason: EvictionReason = EvictionReason.MANUAL
    ) -> ContextItem | None:
        """Remove an item by ID, recording the eviction."""
        item = self._items.pop(item_id, None)
        if item and item_id in self._order:
            self._order.remove(item_id)
            if not item.pinned:
                self._eviction_log.append(
                    EvictionRecord(
                        item_id=item.id,
                        label=item.label,
                        source=item.source,
                        reason=reason,
                        token_count=item.estimated_tokens(),
                    )
                )
        return item

    def pin(self, item_id: str) -> bool:
        """Pin an item so it won't be evicted. Return True on success."""
        item = self._items.get(item_id)
        if item:
            item.pinned = True
            return True
        return False

    def unpin(self, item_id: str) -> bool:
        """Unpin an item. Return True on success."""
        item = self._items.get(item_id)
        if item:
            item.pinned = False
            return True
        return False

    def clear(self, keep_pinned: bool = True) -> int:
        """Remove all items (except pinned if keep_pinned). Return count removed."""
        to_remove = [
            iid for iid in list(self._order) if not (keep_pinned and self._items[iid].pinned)
        ]
        for iid in to_remove:
            self.remove(iid, reason=EvictionReason.SESSION_RESET)
        return len(to_remove)

    # ------------------------------------------------------------------
    # Compression
    # ------------------------------------------------------------------
    def used_tokens(self) -> int:
        """Total tokens currently in the map."""
        return sum(item.estimated_tokens() for item in self._items.values())

    def free_tokens(self) -> int:
        """Remaining token budget."""
        return max(0, self.max_tokens - self.used_tokens())

    def compression_needed(self) -> bool:
        """Return True if used tokens exceed the budget."""
        return self.used_tokens() > self.max_tokens

    def compress(self, reserve_tokens: int = 200) -> list[ContextItem]:
        """Evict unpinned, low-priority items until within budget.

        Items are evicted in priority order (lowest first), and within
        the same priority, oldest first.  Pinned items are never evicted.

        Args:
            reserve_tokens: Keep this many tokens free for new content.

        Returns:
            List of evicted items.
        """
        target = self.max_tokens - reserve_tokens
        if self.used_tokens() <= target:
            return []

        # Candidates: unpinned items sorted by (priority asc, insertion order asc).
        candidates = [
            (self._order.index(iid), item) for iid, item in self._items.items() if not item.pinned
        ]
        candidates.sort(key=lambda x: (x[1].priority, x[0]))

        evicted: list[ContextItem] = []
        for _order_idx, item in candidates:
            if self.used_tokens() <= target:
                break
            removed = self.remove(item.id, reason=EvictionReason.TOKEN_BUDGET)
            if removed:
                evicted.append(removed)

        if evicted:
            logger.info(
                "Context compression evicted %d items, freed ~%d tokens",
                len(evicted),
                sum(i.estimated_tokens() for i in evicted),
            )
        return evicted

    def replace_with_summary(
        self,
        item_ids: list[str],
        summary_content: str,
        summary_label: str = "Compressed history",
    ) -> ContextItem | None:
        """Replace several items with a single summarised item.

        This is the "crystallisation" step: instead of keeping 20 old
        messages, compress them into one structured summary.

        Args:
            item_ids: IDs of items to replace.
            summary_content: The compressed summary text.
            summary_label: Label for the summary item.

        Returns:
            The new summary item, or None if nothing was replaced.
        """
        items_to_replace = [self._items[iid] for iid in item_ids if iid in self._items]
        if not items_to_replace:
            return None

        total_tokens = sum(i.estimated_tokens() for i in items_to_replace)
        for iid in item_ids:
            self.remove(iid, reason=EvictionReason.COMPRESSION)

        summary = self.add(
            source=ContextSource.COMPRESSED_HISTORY,
            label=summary_label,
            content=summary_content,
            priority=60,
            metadata={"replaced_count": len(items_to_replace), "original_tokens": total_tokens},
        )
        logger.info(
            "Compressed %d items (~%d tok) into summary (~%d tok)",
            len(items_to_replace),
            total_tokens,
            summary.estimated_tokens(),
        )
        return summary

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get(self, item_id: str) -> ContextItem | None:
        """Get an item by ID."""
        return self._items.get(item_id)

    def items(self) -> list[ContextItem]:
        """Return all items in order."""
        return [self._items[iid] for iid in self._order if iid in self._items]

    def by_source(self, source: ContextSource) -> list[ContextItem]:
        """Return items from a specific source."""
        return [i for i in self.items() if i.source == source]

    def pinned_items(self) -> list[ContextItem]:
        """Return all pinned items."""
        return [i for i in self.items() if i.pinned]

    def eviction_log(self, limit: int = 20) -> list[EvictionRecord]:
        """Return recent eviction records."""
        return list(reversed(self._eviction_log[-limit:]))

    def source_breakdown(self) -> list[tuple[ContextSource, int, int]]:
        """Return (source, item_count, token_count) per source."""
        counts: dict[ContextSource, list[int]] = {}
        for item in self._items.values():
            counts.setdefault(item.source, [0, 0])
            counts[item.source][0] += 1
            counts[item.source][1] += item.estimated_tokens()
        return [
            (src, data[0], data[1]) for src, data in sorted(counts.items(), key=lambda x: -x[1][1])
        ]

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------
    def render_heatmap(self, width: int = 60) -> str:
        """Render an ASCII heat-map of context window usage.

        Each source gets a coloured/textured bar segment proportional
        to its token usage.  Pinned items are marked with ●.

        Args:
            width: Total width of the bar in characters.

        Returns:
            Multi-line ASCII visualization.
        """
        used = self.used_tokens()
        total = self.max_tokens
        pct = (used / total * 100) if total else 0

        # Build the bar.
        bar_chars: list[str] = []
        source_icons = {
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

        breakdown = self.source_breakdown()
        if breakdown and used > 0:
            for source, _count, tokens in breakdown:
                seg_width = max(1, int(tokens / total * width))
                icon = source_icons.get(source, "?")
                bar_chars.append(icon * seg_width)
        bar = "".join(bar_chars)[:width]
        if len(bar) < width:
            bar += "·" * (width - len(bar))

        lines = [
            f"Context Window: {used:,} / {total:,} tokens ({pct:.1f}%)",
            bar,
            "",
        ]

        # Legend / breakdown.
        lines.append("Source breakdown:")
        for source, count, tokens in breakdown:
            icon = source_icons.get(source, "?")
            pin_mark = " ●" if any(i.pinned for i in self.by_source(source)) else ""
            lines.append(
                f"  {icon} {source.value:25s} {count:2d} items  {tokens:>6,} tok{pin_mark}"
            )

        # Eviction log.
        if self._eviction_log:
            lines.append("")
            lines.append("Recently evicted:")
            for rec in self.eviction_log(5):
                lines.append(
                    f"  ✕ {rec.label[:40]:40s} {rec.token_tokens if hasattr(rec, 'token_tokens') else rec.token_count:>6} tok ({rec.reason.value})"
                )

        # Pinned items.
        pinned = self.pinned_items()
        if pinned:
            lines.append("")
            lines.append("Pinned (never evicted):")
            for item in pinned:
                lines.append(f"  ● {item.label[:50]}")

        return "\n".join(lines)

    def render_item_list(self, max_items: int = 20) -> str:
        """Render a detailed list of items with token counts."""
        items = self.items()
        lines = [
            f"{'ID':<10} {'Source':<22} {'Tokens':>7} {'P':>2} {'Pri':>3}  Label",
            "-" * 80,
        ]
        for item in items[-max_items:]:
            pin = "●" if item.pinned else " "
            lines.append(
                f"{item.id:<10} {item.source.value:<22} "
                f"{item.estimated_tokens():>7,} {pin:>2} {item.priority:>3}  "
                f"{item.label[:40]}"
            )
        if len(items) > max_items:
            lines.append(f"  ... and {len(items) - max_items} more")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def to_messages(self) -> list[dict[str, Any]]:
        """Export items as a list of message dicts ready for the LLM API.

        Pinned items first, then in insertion order.  Hidden items are
        excluded.
        """
        items = sorted(
            [i for i in self.items() if i.visible],
            key=lambda i: (not i.pinned, self._order.index(i.id)),
        )
        messages: list[dict[str, Any]] = []
        for item in items:
            if item.source in (ContextSource.SYSTEM, ContextSource.SOUL):
                messages.append({"role": "system", "content": item.content})
            elif item.source == ContextSource.USER_MESSAGE:
                messages.append({"role": "user", "content": item.content})
            elif item.source in (
                ContextSource.ASSISTANT_MESSAGE,
                ContextSource.TOOL_RESULT,
                ContextSource.COMPRESSED_HISTORY,
            ):
                role = "assistant"
                if item.source == ContextSource.TOOL_RESULT:
                    role = "tool"
                messages.append({"role": role, "content": item.content})
            elif item.source in (
                ContextSource.SKILL,
                ContextSource.MEMORY_RECALL,
                ContextSource.MEMORY_SUMMARY,
                ContextSource.CUSTOM,
                ContextSource.PIPELINE_OUTPUT,
            ):
                # Inject as system context.
                messages.append({"role": "system", "content": item.content})
        return messages
