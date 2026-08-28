"""SQLite database manager for Hermes TUI.

Provides schema initialisation, FTS5 full-text search, simple versioned
migrations, and a thread-safe connection wrapper.
"""

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Bump this whenever the schema changes in a backwards-incompatible way.
SCHEMA_VERSION = 2


class DatabaseManager:
    """Thread-safe SQLite database manager.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._connect()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def _connect(self) -> None:
        """Open the SQLite connection with sensible defaults."""
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        logger.debug("Database connected: %s", self.db_path)
        # Ensure schema exists so callers don't have to remember.
        self.init_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the underlying SQLite connection, reconnecting if needed."""
        if self._conn is None:
            self._connect()
        assert self._conn is not None
        return self._conn

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        """Context manager yielding a cursor with serialised writes."""
        with self._lock:
            cur = self.connection.cursor()
            try:
                yield cur
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
            finally:
                cur.close()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.debug("Database connection closed")

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema / migrations
    # ------------------------------------------------------------------
    def init_schema(self) -> None:
        """Create all tables, indexes, and FTS triggers if missing."""
        with self.cursor() as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id           TEXT PRIMARY KEY,
                    layer        TEXT NOT NULL,
                    key          TEXT DEFAULT '',
                    content      TEXT NOT NULL,
                    tags         TEXT DEFAULT '',
                    metadata     TEXT DEFAULT '{}',
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id            TEXT PRIMARY KEY,
                    title         TEXT DEFAULT '',
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id           TEXT PRIMARY KEY,
                    session_id   TEXT NOT NULL,
                    role         TEXT NOT NULL,
                    content      TEXT DEFAULT '',
                    tool_calls   TEXT DEFAULT '[]',
                    tool_call_id TEXT DEFAULT '',
                    name         TEXT DEFAULT '',
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS skills_meta (
                    name        TEXT PRIMARY KEY,
                    description TEXT DEFAULT '',
                    version     TEXT DEFAULT '1.0.0',
                    file_path   TEXT DEFAULT '',
                    tags        TEXT DEFAULT '[]',
                    enabled     INTEGER DEFAULT 1,
                    last_used   TIMESTAMP,
                    use_count   INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_memories_layer ON memories(layer);
                CREATE INDEX IF NOT EXISTS idx_memories_key   ON memories(key);
                CREATE INDEX IF NOT EXISTS idx_messages_sid   ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
                """
            )

            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories_fts_map (
                    fts_rowid  INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id  TEXT UNIQUE,
                    content    TEXT,
                    key        TEXT,
                    tags       TEXT
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(content, key, tags);

                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories
                BEGIN
                    INSERT INTO memories_fts_map(memory_id, content, key, tags)
                    VALUES (new.id, new.content, new.key, new.tags);
                    INSERT INTO memories_fts(rowid, content, key, tags)
                    VALUES (last_insert_rowid(), new.content, new.key, new.tags);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_ad BEFORE DELETE ON memories
                BEGIN
                    DELETE FROM memories_fts WHERE rowid IN (
                        SELECT fts_rowid FROM memories_fts_map
                        WHERE memory_id = old.id
                    );
                    DELETE FROM memories_fts_map WHERE memory_id = old.id;
                END;
                """
            )

        logger.info("Database schema initialised")
        self.migrate()

    def migrate(self) -> None:
        """Record the schema version (baseline v2)."""
        with self.cursor() as cur:
            cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            cur.execute(
                "INSERT INTO schema_version (version) SELECT ? "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_version WHERE version=?)",
                (SCHEMA_VERSION, SCHEMA_VERSION),
            )
        logger.info("Database migrated to v%s", SCHEMA_VERSION)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------
    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> sqlite3.Cursor:
        """Execute a single statement and return the cursor."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur

    def fetch_one(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> sqlite3.Row | None:
        """Execute a query and return the first row (or ``None``)."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()  # type: ignore[no-any-return]

    def fetch_all(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> list[sqlite3.Row]:
        """Execute a query and return all rows."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    # ------------------------------------------------------------------
    # High-level CRUD helpers (used by the test suite and higher layers)
    # ------------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        """Return the live SQLite connection (alias for :attr:`connection`)."""
        return self.connection

    # -- memories -------------------------------------------------------
    def insert_memory(
        self,
        memory_id: str,
        layer: str,
        content: str,
        key: str = "",
        tags: str = "",
        metadata: str = "{}",
    ) -> str:
        now = datetime.now(UTC).isoformat()
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO memories (id,layer,key,content,tags,metadata,"
                "created_at,accessed_at,access_count) VALUES (?,?,?,?,?,?,?,?,0)",
                (memory_id, layer, key, content, tags, metadata, now, now),
            )
        return memory_id

    def get_memory(self, memory_id: str) -> sqlite3.Row | None:
        row = self.fetch_one("SELECT * FROM memories WHERE id=?", (memory_id,))
        if row is not None:
            self.execute(
                "UPDATE memories SET accessed_at=?, access_count=access_count+1 WHERE id=?",
                (datetime.now(UTC), memory_id),
            )
            row = self.fetch_one("SELECT * FROM memories WHERE id=?", (memory_id,))
        return row

    def get_memory_by_key(self, key: str) -> sqlite3.Row | None:
        return self.fetch_one(
            "SELECT * FROM memories WHERE key=? ORDER BY created_at DESC, id DESC LIMIT 1", (key,)
        )

    def search_memories(
        self, query: str, layer: str | None = None, limit: int = 10
    ) -> list[sqlite3.Row]:
        """Full-text search memories with LIKE fallback for CJK text."""
        # FTS5 MATCH works well for tokenised languages but not for CJK.
        # Try FTS first; if no results, fall back to LIKE.
        sql = (
            "SELECT m.* FROM memories m "
            "JOIN memories_fts_map fmap ON fmap.memory_id = m.id "
            "JOIN memories_fts f ON f.rowid = fmap.fts_rowid "
            "WHERE f.memories_fts MATCH ? "
        )
        params: list[Any] = [query]
        if layer:
            sql += "AND m.layer=? "
            params.append(layer)
        sql += "ORDER BY rank LIMIT ?"
        params.append(limit)
        rows = self.fetch_all(sql, tuple(params))
        if rows:
            return rows

        # Fallback: LIKE search across content / key / tags
        like_sql = "SELECT * FROM memories WHERE (content LIKE ? OR key LIKE ? OR tags LIKE ?) "
        like_params: list[Any] = [f"%{query}%"] * 3
        if layer:
            like_sql += "AND layer=? "
            like_params.append(layer)
        like_sql += "ORDER BY created_at DESC LIMIT ?"
        like_params.append(limit)
        return self.fetch_all(like_sql, tuple(like_params))

    def count_memories(self, layer: str | None = None) -> int:
        if layer:
            row = self.fetch_one("SELECT COUNT(*) AS cnt FROM memories WHERE layer=?", (layer,))
        else:
            row = self.fetch_one("SELECT COUNT(*) AS cnt FROM memories")
        return row["cnt"] if row else 0

    def prune_oldest(self, keep: int, layer: str | None = None) -> int:
        total = self.count_memories(layer)
        if total <= keep:
            return 0
        over = total - keep
        if layer:
            self.execute(
                "DELETE FROM memories WHERE id IN (SELECT id FROM memories "
                "WHERE layer=? ORDER BY accessed_at ASC, created_at ASC LIMIT ?)",
                (layer, over),
            )
        else:
            self.execute(
                "DELETE FROM memories WHERE id IN (SELECT id FROM memories "
                "ORDER BY accessed_at ASC, created_at ASC LIMIT ?)",
                (over,),
            )
        return over

    def clear_memories(self, layer: str | None = None) -> int:
        n = self.count_memories(layer)
        if layer:
            self.execute("DELETE FROM memories WHERE layer=?", (layer,))
        else:
            self.execute("DELETE FROM memories")
        return n

    # -- sessions -------------------------------------------------------
    def create_session(self, session_id: str, title: str = "") -> None:
        self.execute(
            "INSERT OR IGNORE INTO sessions (id,title,message_count) VALUES (?,?,0)",
            (session_id, title),
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.fetch_one("SELECT * FROM sessions WHERE id=?", (session_id,))
        return dict(row) if row else None

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM sessions ORDER BY updated_at DESC, id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        cur = self.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return cur.rowcount > 0

    def update_session_title(self, session_id: str, title: str) -> None:
        self.execute(
            "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
            (title, datetime.now(UTC), session_id),
        )

    # -- messages -------------------------------------------------------
    def insert_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Any = None,
        tool_call_id: str = "",
        name: str = "",
    ) -> str:
        if not isinstance(tool_calls, str):
            import json as _json

            tool_calls = _json.dumps(tool_calls or [], ensure_ascii=False)
        now = datetime.now(UTC)
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id,session_id,role,content,tool_calls,"
                "tool_call_id,name,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (message_id, session_id, role, content, tool_calls, tool_call_id, name, now),
            )
            cur.execute(
                "UPDATE sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
                (now, session_id),
            )
        return message_id

    def get_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM messages WHERE session_id=? ORDER BY created_at ASC, id ASC LIMIT ?",
            (session_id, limit),
        )
        out: list[dict[str, Any]] = []
        import json as _json

        for r in rows:
            d = dict(r)
            try:
                d["tool_calls"] = _json.loads(d.get("tool_calls") or "[]")
            except (ValueError, TypeError):
                d["tool_calls"] = []
            out.append(d)
        return out

    # -- skills meta ----------------------------------------------------
    def upsert_skill_meta(
        self,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        file_path: str = "",
        tags: Any = None,
        enabled: bool = True,
    ) -> None:
        import json as _json

        if not isinstance(tags, str):
            tags = _json.dumps(tags or [], ensure_ascii=False)
        now = datetime.now(UTC)
        self.execute(
            "INSERT INTO skills_meta (name,description,version,file_path,tags,"
            "enabled,last_used) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "description=excluded.description, version=excluded.version, "
            "file_path=excluded.file_path, tags=excluded.tags, "
            "enabled=excluded.enabled",
            (name, description, version, file_path, tags, int(bool(enabled)), now),
        )

    def get_skill_meta(self, name: str) -> dict[str, Any] | None:
        row = self.fetch_one("SELECT * FROM skills_meta WHERE name=?", (name,))
        if row is None:
            return None
        d = dict(row)
        import json as _json

        try:
            d["tags"] = _json.loads(d.get("tags") or "[]")
        except (ValueError, TypeError):
            d["tags"] = []
        d["enabled"] = bool(d.get("enabled"))
        return d

    def list_skills_meta(self) -> list[dict[str, Any]]:
        rows = self.fetch_all("SELECT * FROM skills_meta ORDER BY name")
        out: list[dict[str, Any]] = []
        import json as _json

        for r in rows:
            d = dict(r)
            try:
                d["tags"] = _json.loads(d.get("tags") or "[]")
            except (ValueError, TypeError):
                d["tags"] = []
            d["enabled"] = bool(d.get("enabled"))
            out.append(d)
        return out

    def set_skill_enabled(self, name: str, enabled: bool) -> None:
        self.execute("UPDATE skills_meta SET enabled=? WHERE name=?", (int(bool(enabled)), name))

    def increment_skill_use_count(self, name: str) -> None:
        self.execute(
            "UPDATE skills_meta SET use_count=use_count+1, last_used=? WHERE name=?",
            (datetime.now(UTC), name),
        )

    @property
    def schema_version(self) -> int:
        row = self.fetch_one("SELECT version FROM schema_version ORDER BY rowid DESC LIMIT 1")
        return row["version"] if row else 0
