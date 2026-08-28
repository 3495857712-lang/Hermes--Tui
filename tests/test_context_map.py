"""Tests for the Context Map module."""

from __future__ import annotations

import pytest

from hermes_tui.context_map import (
    ContextItem,
    ContextMap,
    ContextSource,
    EvictionReason,
)


@pytest.fixture()
def cm() -> ContextMap:
    return ContextMap(max_tokens=1000)


class TestAddAndRemove:
    def test_add_item(self, cm: ContextMap) -> None:
        item = cm.add(ContextSource.USER_MESSAGE, "Hello", "Hello world", token_count=10)
        assert item.id.startswith("ctx-")
        assert item.estimated_tokens() == 10
        assert len(cm.items()) == 1

    def test_add_auto_estimates_tokens(self, cm: ContextMap) -> None:
        item = cm.add(ContextSource.SYSTEM, "Sys", "x" * 400)
        # 400 chars / 4 = 100 tokens
        assert item.estimated_tokens() == 100

    def test_remove_item(self, cm: ContextMap) -> None:
        item = cm.add(ContextSource.USER_MESSAGE, "Hello", "Hello")
        removed = cm.remove(item.id)
        assert removed is not None
        assert removed.id == item.id
        assert len(cm.items()) == 0

    def test_remove_nonexistent(self, cm: ContextMap) -> None:
        result = cm.remove("nonexistent")
        assert result is None

    def test_remove_records_eviction(self, cm: ContextMap) -> None:
        item = cm.add(ContextSource.USER_MESSAGE, "Hello", "Hello", token_count=10)
        cm.remove(item.id, reason=EvictionReason.MANUAL)
        log = cm.eviction_log()
        assert len(log) == 1
        assert log[0].reason == EvictionReason.MANUAL

    def test_replace_same_id(self, cm: ContextMap) -> None:
        cm.add(ContextSource.USER_MESSAGE, "V1", "version 1", item_id="fixed")
        cm.add(ContextSource.USER_MESSAGE, "V2", "version 2", item_id="fixed")
        items = cm.items()
        assert len(items) == 1
        assert items[0].label == "V2"
        # Old version should be in eviction log.
        assert len(cm.eviction_log()) == 1


class TestPinning:
    def test_pin_item(self, cm: ContextMap) -> None:
        item = cm.add(ContextSource.SYSTEM, "System", "sys prompt", token_count=100)
        assert cm.pin(item.id) is True
        assert item.pinned is True

    def test_unpin_item(self, cm: ContextMap) -> None:
        item = cm.add(ContextSource.SYSTEM, "System", "sys", token_count=100, pinned=True)
        assert cm.unpin(item.id) is True
        assert item.pinned is False

    def test_pin_nonexistent(self, cm: ContextMap) -> None:
        assert cm.pin("nope") is False

    def test_pinned_items_list(self, cm: ContextMap) -> None:
        cm.add(ContextSource.SYSTEM, "S1", "s1", pinned=True)
        cm.add(ContextSource.USER_MESSAGE, "U1", "u1")
        cm.add(ContextSource.SYSTEM, "S2", "s2", pinned=True)
        pinned = cm.pinned_items()
        assert len(pinned) == 2


class TestTokenBudget:
    def test_used_tokens(self, cm: ContextMap) -> None:
        cm.add(ContextSource.USER_MESSAGE, "U1", "u" * 400)  # 100 tokens
        cm.add(ContextSource.ASSISTANT_MESSAGE, "A1", "a" * 800)  # 200 tokens
        assert cm.used_tokens() == 300

    def test_free_tokens(self, cm: ContextMap) -> None:
        cm.add(ContextSource.USER_MESSAGE, "U1", "u" * 400)  # 100
        assert cm.free_tokens() == 900

    def test_compression_needed(self, cm: ContextMap) -> None:
        assert cm.compression_needed() is False
        cm.add(ContextSource.USER_MESSAGE, "Big", "x" * 5000)
        assert cm.compression_needed() is True

    def test_compress_evicts_low_priority(self, cm: ContextMap) -> None:
        # Add a high-priority pinned item.
        cm.add(
            ContextSource.SYSTEM,
            "System",
            "system",
            token_count=200,
            pinned=True,
            priority=100,
        )
        # Add many low-priority items.
        for i in range(20):
            cm.add(
                ContextSource.USER_MESSAGE,
                f"Item {i}",
                f"content {i}" * 50,
                priority=10,
            )
        assert cm.compression_needed()
        evicted = cm.compress(reserve_tokens=100)
        assert len(evicted) > 0
        # Pinned item should still be there.
        assert cm.by_source(ContextSource.SYSTEM)
        assert cm.used_tokens() <= 1000 - 100

    def test_compress_never_evicts_pinned(self, cm: ContextMap) -> None:
        for i in range(5):
            cm.add(
                ContextSource.SYSTEM,
                f"Pinned {i}",
                f"p{i}" * 100,
                pinned=True,
                priority=100,
            )
        evicted = cm.compress(reserve_tokens=0)
        # If all items are pinned and over budget, nothing can be evicted.
        pinned_count = len(cm.pinned_items())
        assert pinned_count == 5

    def test_compress_noop_when_under_budget(self, cm: ContextMap) -> None:
        cm.add(ContextSource.USER_MESSAGE, "Small", "hi", token_count=10)
        evicted = cm.compress()
        assert evicted == []


class TestCompressionSummary:
    def test_replace_with_summary(self, cm: ContextMap) -> None:
        old_items = []
        for i in range(5):
            item = cm.add(
                ContextSource.ASSISTANT_MESSAGE,
                f"Old {i}",
                f"old content {i}" * 20,
            )
            old_items.append(item.id)

        old_total = cm.used_tokens()
        summary = cm.replace_with_summary(
            old_items,
            "Summary of 5 old messages",
            summary_label="Test summary",
        )
        assert summary is not None
        assert summary.source == ContextSource.COMPRESSED_HISTORY
        assert cm.used_tokens() < old_total


class TestSourceBreakdown:
    def test_breakdown(self, cm: ContextMap) -> None:
        cm.add(ContextSource.USER_MESSAGE, "U1", "u", token_count=50)
        cm.add(ContextSource.USER_MESSAGE, "U2", "u", token_count=30)
        cm.add(ContextSource.SYSTEM, "S1", "s", token_count=20)
        breakdown = cm.source_breakdown()
        sources = {b[0] for b in breakdown}
        assert ContextSource.USER_MESSAGE in sources
        assert ContextSource.SYSTEM in sources
        for source, count, tokens in breakdown:
            if source == ContextSource.USER_MESSAGE:
                assert count == 2
                assert tokens == 80


class TestClear:
    def test_clear_keeps_pinned(self, cm: ContextMap) -> None:
        cm.add(ContextSource.SYSTEM, "Pinned", "p", pinned=True)
        cm.add(ContextSource.USER_MESSAGE, "Regular", "r")
        removed = cm.clear(keep_pinned=True)
        assert removed == 1
        assert len(cm.pinned_items()) == 1

    def test_clear_removes_all(self, cm: ContextMap) -> None:
        cm.add(ContextSource.SYSTEM, "Pinned", "p", pinned=True)
        cm.add(ContextSource.USER_MESSAGE, "Regular", "r")
        removed = cm.clear(keep_pinned=False)
        assert removed == 2
        assert len(cm.items()) == 0


class TestExport:
    def test_to_messages(self, cm: ContextMap) -> None:
        cm.add(ContextSource.SYSTEM, "System", "You are helpful")
        cm.add(ContextSource.USER_MESSAGE, "User", "Hello")
        cm.add(ContextSource.ASSISTANT_MESSAGE, "Assistant", "Hi!")
        msgs = cm.to_messages()
        assert len(msgs) == 3
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[2]["role"] == "assistant"

    def test_hidden_items_excluded(self, cm: ContextMap) -> None:
        cm.add(ContextSource.SYSTEM, "Visible", "v", visible=True)
        cm.add(ContextSource.SYSTEM, "Hidden", "h", visible=False)
        msgs = cm.to_messages()
        assert len(msgs) == 1


class TestRendering:
    def test_render_heatmap_empty(self, cm: ContextMap) -> None:
        output = cm.render_heatmap()
        assert "0" in output
        assert "Context Window" in output

    def test_render_heatmap_with_items(self, cm: ContextMap) -> None:
        cm.add(ContextSource.SYSTEM, "System", "sys", token_count=100, pinned=True)
        cm.add(ContextSource.USER_MESSAGE, "User", "hello", token_count=50)
        output = cm.render_heatmap()
        assert "system" in output.lower()
        assert "user_message" in output.lower()
        assert "Pinned" in output

    def test_render_item_list(self, cm: ContextMap) -> None:
        cm.add(ContextSource.USER_MESSAGE, "Test", "content")
        output = cm.render_item_list()
        assert "Test" in output
        assert "Source" in output
