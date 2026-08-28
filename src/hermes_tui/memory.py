"""Three-layer memory system for Hermes TUI.

Layers
------
* ``working``    - short-lived context for the current turn.
* ``episodic``   - conversation-derived facts, pruned when the cap is hit.
* ``procedural`` - durable "how-to" knowledge and user preferences.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .database import DatabaseManager
from .utils.helpers import approx_token_count, detect_prompt_injection, generate_id

logger = logging.getLogger(__name__)

# Layer name constants (public API).
LAYER_WORKING = "working"
LAYER_EPISODIC = "episodic"
LAYER_PROCEDURAL = "procedural"

_VALID_LAYERS = {LAYER_WORKING, LAYER_EPISODIC, LAYER_PROCEDURAL}

_MEMORY_KEYWORDS = (
    "记住",
    "别忘了",
    "记得",
    "我的",
    "我偏好",
    "我喜欢",
    "我不喜欢",
    "我叫",
    "我是",
    "remember",
    "don't forget",
    "my name",
    "i prefer",
    "i like",
    "i always",
    "note that",
    "keep in mind",
)


@dataclass
class MemoryEntry:
    """A single memory record."""

    layer: str
    content: str
    key: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | str | None = None
    created_at: datetime | None = None
    accessed_at: datetime | None = None
    access_count: int = 0
    potential_injection: bool = False

    def __post_init__(self) -> None:
        if self.layer not in _VALID_LAYERS:
            raise ValueError(
                f"Invalid layer '{self.layer}'. Must be one of: {sorted(_VALID_LAYERS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "layer": self.layer,
            "key": self.key,
            "content": self.content,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "access_count": self.access_count,
        }

    @classmethod
    def from_row(cls, row: Any) -> MemoryEntry:
        tags_raw = row["tags"] or ""
        tags = [t for t in tags_raw.split(",") if t] if tags_raw else []
        meta: dict[str, Any] = {}
        meta_raw = row["metadata"] if "metadata" in row.keys() else None
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        return cls(
            id=row["id"],
            layer=row["layer"],
            key=row["key"],
            content=row["content"],
            tags=tags,
            metadata=meta,
            created_at=row["created_at"],
            accessed_at=row["accessed_at"],
            access_count=row["access_count"] or 0,
        )


class MemoryManager:
    """High-level API for the three-layer memory system."""

    def __init__(
        self,
        db: DatabaseManager,
        max_entries: int = 1000,
        auto_prune: bool = True,
    ) -> None:
        self.db = db
        self.max_entries = max_entries
        self.auto_prune = auto_prune

    # -- low-level add --------------------------------------------------

    def add(
        self,
        content: str,
        layer: str = LAYER_EPISODIC,
        key: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Store a new memory, rejecting prompt-injection content."""
        detected, patterns = detect_prompt_injection(content)
        if detected:
            raise ValueError(f"Potential prompt injection detected in memory: {patterns}")
        tag_str = ",".join(tags or [])
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        now = datetime.now(UTC)
        mid = generate_id()
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO memories (id,layer,key,content,tags,metadata,"
                "created_at,accessed_at,access_count) VALUES (?,?,?,?,?,?,?,?,0)",
                (mid, layer, key, content, tag_str, meta_str, now, now),
            )
        entry = MemoryEntry(
            id=mid,
            layer=layer,
            key=key,
            content=content,
            tags=tags or [],
            metadata=metadata or {},
            created_at=now,
            accessed_at=now,
        )
        if self.auto_prune:
            self.prune(keep=self.max_entries)
        return entry

    # -- convenience layer methods --------------------------------------

    def add_episodic_memory(
        self,
        content: str,
        key: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        auto_key = key or content[:40].strip()
        return self.add(content, layer=LAYER_EPISODIC, key=auto_key, tags=tags or ["episodic"])

    def add_working_memory(
        self,
        content: str,
        key: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        auto_key = key or content[:40].strip()
        return self.add(content, layer=LAYER_WORKING, key=auto_key, tags=tags or ["working"])

    def add_procedural_memory(
        self,
        content: str,
        key: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        auto_key = key or content[:40].strip()
        return self.add(content, layer=LAYER_PROCEDURAL, key=auto_key, tags=tags or ["procedural"])

    # -- retrieval ------------------------------------------------------

    def get(self, memory_id: int | str) -> MemoryEntry | None:
        """Retrieve a memory by numeric id and bump its access count."""
        row = self.db.fetch_one("SELECT * FROM memories WHERE id=?", (memory_id,))
        if row is None:
            return None
        self._bump_access(memory_id)
        return MemoryEntry.from_row(row)

    def get_by_key(self, key: str) -> MemoryEntry | None:
        row = self.db.fetch_one(
            "SELECT * FROM memories WHERE key=? ORDER BY id DESC LIMIT 1", (key,)
        )
        if row is None:
            return None
        self._bump_access(row["id"])
        return MemoryEntry.from_row(row)

    def search(
        self,
        query: str,
        layer: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Full-text search over memories (FTS5 with LIKE fallback for CJK)."""
        rows = self.db.search_memories(query, layer=layer, limit=limit)
        entries = [MemoryEntry.from_row(r) for r in rows]
        for e in entries:
            if e.id is not None:
                self._bump_access(e.id)
        return entries

    def get_recent(
        self,
        layer: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        sql = "SELECT * FROM memories"
        params: list[Any] = []
        if layer:
            sql += " WHERE layer=?"
            params.append(layer)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [MemoryEntry.from_row(r) for r in self.db.fetch_all(sql, tuple(params))]

    # -- access bookkeeping ---------------------------------------------

    def _bump_access(self, memory_id: int | str) -> None:
        self.db.execute(
            "UPDATE memories SET accessed_at=?, access_count=access_count+1 WHERE id=?",
            (datetime.now(UTC), memory_id),
        )

    # -- maintenance ----------------------------------------------------

    def prune(self, keep: int = 1000, layer: str | None = None) -> int:
        """Delete oldest entries so total (or per-layer) count <= *keep*.

        Returns the number of deleted rows.
        """
        if layer:
            row = self.db.fetch_one("SELECT COUNT(*) AS cnt FROM memories WHERE layer=?", (layer,))
        else:
            row = self.db.fetch_one("SELECT COUNT(*) AS cnt FROM memories")
        total = row["cnt"] if row else 0
        if total <= keep:
            return 0
        over = total - keep
        if layer:
            self.db.execute(
                "DELETE FROM memories WHERE id IN ("
                "SELECT id FROM memories WHERE layer=? "
                "ORDER BY accessed_at ASC, id ASC LIMIT ?)",
                (layer, over),
            )
        else:
            self.db.execute(
                "DELETE FROM memories WHERE id IN ("
                "SELECT id FROM memories ORDER BY accessed_at ASC, id ASC LIMIT ?)",
                (over,),
            )
        logger.info("Pruned %s memories", over)
        return over

    def clear(self, layer: str | None = None) -> int:
        """Delete memories; returns deleted count."""
        n = self.count(layer)
        if layer:
            self.db.execute("DELETE FROM memories WHERE layer=?", (layer,))
        else:
            self.db.execute("DELETE FROM memories")
        return n

    def count(self, layer: str | None = None) -> int:
        if layer:
            row = self.db.fetch_one("SELECT COUNT(*) AS cnt FROM memories WHERE layer=?", (layer,))
        else:
            row = self.db.fetch_one("SELECT COUNT(*) AS cnt FROM memories")
        return row["cnt"] if row else 0

    # -- extraction / summary -------------------------------------------

    def extract_from_messages(
        self,
        messages: Iterable[dict[str, Any] | Any],
    ) -> list[MemoryEntry]:
        """Extract episodic memories from messages containing keywords."""
        created: list[MemoryEntry] = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "") or ""
            else:
                role = getattr(msg, "role", "")
                content = getattr(msg, "content", "") or ""
            if role != "user" or not content:
                continue
            if any(kw in content.lower() for kw in _MEMORY_KEYWORDS):
                try:
                    created.append(self.add_episodic_memory(content))
                except ValueError:
                    continue
        return created

    # Back-compat alias used elsewhere.
    def extract_and_store(self, messages: Iterable[Any]) -> int:
        return len(self.extract_from_messages(messages))

    def context_summary(self, max_tokens: int = 2000) -> str:
        """Build a compact textual summary of recent memories."""
        working = self.get_recent(layer=LAYER_WORKING, limit=10)
        episodic = self.get_recent(layer=LAYER_EPISODIC, limit=10)
        procedural = self.get_recent(layer=LAYER_PROCEDURAL, limit=10)
        if not (working or episodic or procedural):
            return "(no memories)"

        parts: list[str] = []
        budget = max_tokens

        def _add_section(title: str, items: list[MemoryEntry]) -> None:
            if not items:
                return
            section = [f"## {title}"]
            for m in items:
                line = f"- {m.content}"
                if approx_token_count("\n".join(parts + section + [line])) > budget:
                    break
                section.append(line)
            parts.extend(section)

        _add_section("Current context", working)
        _add_section("Persistent memories", episodic)
        _add_section("Durable knowledge", procedural)
        return "\n".join(parts)

    def get_context_summary(self, max_tokens: int = 2000) -> str:
        return self.context_summary(max_tokens=max_tokens)
