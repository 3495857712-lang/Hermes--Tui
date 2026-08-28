"""Tests for hermes_tui.database module."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from hermes_tui.database import SCHEMA_VERSION, DatabaseManager
from hermes_tui.utils.helpers import generate_id


@pytest.fixture()
def db(tmp_db_path: Path) -> DatabaseManager:
    """Create a fresh DatabaseManager for each test."""
    manager = DatabaseManager(tmp_db_path)
    yield manager
    manager.close()


class TestInitSchema:
    """Tests for database initialisation."""

    def test_init_schema(self, db: DatabaseManager) -> None:
        """All expected tables should be created."""
        conn = db._get_conn()
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "memories" in tables
        assert "sessions" in tables
        assert "messages" in tables
        assert "skills_meta" in tables
        assert "schema_version" in tables

    def test_migration(self, db: DatabaseManager) -> None:
        """The schema version should be set to the current version."""
        assert db.schema_version == SCHEMA_VERSION

    def test_fts_table_exists(self, db: DatabaseManager) -> None:
        """The FTS5 virtual table should be created."""
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
        ).fetchall()
        assert len(rows) == 1


class TestMemoryCRUD:
    """Tests for memory insert and retrieval."""

    def test_insert_and_get_memory(self, db: DatabaseManager) -> None:
        """Inserting a memory and getting it by ID should return the data."""
        mid = generate_id()
        db.insert_memory(mid, layer="episodic", content="User prefers dark mode")

        row = db.get_memory(mid)
        assert row is not None
        assert row["id"] == mid
        assert row["content"] == "User prefers dark mode"
        assert row["layer"] == "episodic"
        assert row["access_count"] == 1

    def test_get_nonexistent_memory(self, db: DatabaseManager) -> None:
        """Getting a non-existent ID should return None."""
        assert db.get_memory("does-not-exist") is None

    def test_fts_search(self, db: DatabaseManager) -> None:
        """FTS5 full-text search should find matching memories."""
        db.insert_memory(generate_id(), "episodic", "The cat sat on the mat")
        db.insert_memory(generate_id(), "episodic", "Dogs love playing fetch")
        db.insert_memory(generate_id(), "working", "Project deadline is Friday")

        results = db.search_memories("cat")
        assert len(results) == 1
        assert "cat" in results[0]["content"].lower()

        results = db.search_memories("deadline")
        assert len(results) == 1
        assert "friday" in results[0]["content"].lower()

    def test_fts_search_no_results(self, db: DatabaseManager) -> None:
        """Search for a non-existent term should return an empty list."""
        db.insert_memory(generate_id(), "episodic", "Hello world")
        assert db.search_memories("xyznonexistent") == []

    def test_fts_trigger(self, db: DatabaseManager) -> None:
        """Inserting a memory should automatically populate the FTS table."""
        content = "Unique marker for FTS trigger test"
        db.insert_memory(generate_id(), "episodic", content)

        results = db.search_memories("marker")
        assert len(results) == 1
        assert results[0]["content"] == content

    def test_get_memory_by_key(self, db: DatabaseManager) -> None:
        """Getting memory by key should return the latest matching entry."""
        db.insert_memory(generate_id(), "semantic", "Python 3.11", key="python_version")
        db.insert_memory(generate_id(), "semantic", "Python 3.12", key="python_version")

        row = db.get_memory_by_key("python_version")
        assert row is not None
        assert row["content"] == "Python 3.12"

    def test_memory_access_count(self, db: DatabaseManager) -> None:
        """Access count should increment each time a memory is retrieved."""
        mid = generate_id()
        db.insert_memory(mid, "episodic", "Test memory")

        db.get_memory(mid)
        row1 = db.get_memory(mid)
        assert row1["access_count"] >= 2


class TestSessionCRUD:
    """Tests for session create, read, update, delete."""

    def test_session_crud(self, db: DatabaseManager) -> None:
        """Sessions should support create, get, list, update, and delete."""
        sid = generate_id()
        db.create_session(sid, title="Test Session")

        session = db.get_session(sid)
        assert session is not None
        assert session["title"] == "Test Session"

        sessions = db.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == sid

        db.update_session_title(sid, "Updated Title")
        session = db.get_session(sid)
        assert session["title"] == "Updated Title"

        assert db.delete_session(sid) is True
        assert db.get_session(sid) is None
        assert db.list_sessions() == []

    def test_delete_nonexistent_session(self, db: DatabaseManager) -> None:
        """Deleting a non-existent session should return False."""
        assert db.delete_session("nope") is False


class TestMessages:
    """Tests for message insertion and retrieval."""

    def test_message_insert(self, db: DatabaseManager) -> None:
        """Messages should be inserted and retrievable by session."""
        sid = generate_id()
        db.create_session(sid)
        db.insert_message(generate_id(), sid, "user", "Hello")
        db.insert_message(generate_id(), sid, "assistant", "Hi there!")

        msgs = db.get_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert msgs[1]["role"] == "assistant"

    def test_message_with_tool_calls(self, db: DatabaseManager) -> None:
        """Messages with tool_calls JSON should be stored and retrieved."""
        sid = generate_id()
        db.create_session(sid)
        tool_calls = [{"id": "call_1", "function": {"name": "get_time", "arguments": "{}"}}]
        db.insert_message(
            generate_id(),
            sid,
            "assistant",
            "",
            tool_calls=tool_calls,
        )
        msgs = db.get_messages(sid)
        assert len(msgs) == 1
        assert msgs[0]["tool_calls"] == tool_calls

    def test_delete_session_cascades_messages(self, db: DatabaseManager) -> None:
        """Deleting a session should also delete its messages (CASCADE)."""
        sid = generate_id()
        db.create_session(sid)
        db.insert_message(generate_id(), sid, "user", "Hello")
        db.insert_message(generate_id(), sid, "assistant", "Hi!")

        db.delete_session(sid)
        assert db.get_messages(sid) == []


class TestSkillsMeta:
    """Tests for skills_meta table CRUD."""

    def test_skills_meta_crud(self, db: DatabaseManager) -> None:
        """skills_meta should support upsert, get, list, and toggle."""
        db.upsert_skill_meta(
            "weather",
            description="Get weather",
            tags=["weather", "forecast"],
            file_path="/skills/weather/SKILL.md",
        )

        meta = db.get_skill_meta("weather")
        assert meta is not None
        assert meta["description"] == "Get weather"
        assert "weather" in meta["tags"]
        assert meta["enabled"] is True
        assert meta["use_count"] == 0

        db.increment_skill_use_count("weather")
        db.increment_skill_use_count("weather")
        meta = db.get_skill_meta("weather")
        assert meta["use_count"] == 2

        db.set_skill_enabled("weather", False)
        meta = db.get_skill_meta("weather")
        assert meta["enabled"] is False

        db.upsert_skill_meta("weather", description="Updated weather skill")
        meta = db.get_skill_meta("weather")
        assert meta["description"] == "Updated weather skill"

        all_skills = db.list_skills_meta()
        assert len(all_skills) == 1

    def test_get_nonexistent_skill_meta(self, db: DatabaseManager) -> None:
        """Getting non-existent skill meta should return None."""
        assert db.get_skill_meta("nope") is None


class TestPruneAndClear:
    """Tests for pruning and clearing memories."""

    def test_prune_old_memories(self, db: DatabaseManager) -> None:
        """Pruning should delete the oldest entries, keeping the specified number."""
        for i in range(10):
            db.insert_memory(generate_id(), "episodic", f"Memory {i}")

        deleted = db.prune_oldest(5)
        assert deleted == 5
        assert db.count_memories() == 5

    def test_clear_memories(self, db: DatabaseManager) -> None:
        """Clearing all memories should remove every entry."""
        db.insert_memory(generate_id(), "episodic", "A")
        db.insert_memory(generate_id(), "working", "B")

        count = db.clear_memories()
        assert count == 2
        assert db.count_memories() == 0

    def test_clear_layer(self, db: DatabaseManager) -> None:
        """Clearing a specific layer should only affect that layer."""
        db.insert_memory(generate_id(), "episodic", "A")
        db.insert_memory(generate_id(), "working", "B")

        db.clear_memories(layer="episodic")
        assert db.count_memories(layer="episodic") == 0
        assert db.count_memories(layer="working") == 1


class TestThreadSafety:
    """Tests for concurrent database access."""

    def test_thread_safety(self, tmp_db_path: Path) -> None:
        """Multiple threads writing simultaneously should not raise errors."""
        db = DatabaseManager(tmp_db_path)
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(20):
                    db.insert_memory(
                        generate_id(),
                        "episodic",
                        f"Thread {thread_id} memory {i}",
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert db.count_memories() == 100
        db.close()
