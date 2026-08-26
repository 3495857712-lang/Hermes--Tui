"""Tests for the Memory Git module."""

from __future__ import annotations

import pytest

from hermes_tui.memory_git import MemoryDiff, MemoryGit


@pytest.fixture()
def mg() -> MemoryGit:
    return MemoryGit()


class TestInitialState:
    def test_starts_with_initial_commit(self, mg: MemoryGit) -> None:
        log = mg.log()
        assert len(log) == 1
        assert log[0].message == "Initial empty memory"
        assert log[0].author == "system"

    def test_starts_on_main_branch(self, mg: MemoryGit) -> None:
        assert mg.current_branch == "main"
        branches = mg.list_branches()
        assert len(branches) == 1
        assert branches[0][0] == "main"

    def test_initial_state_empty(self, mg: MemoryGit) -> None:
        assert mg.state == {}


class TestCommit:
    def test_stage_and_commit(self, mg: MemoryGit) -> None:
        mg.stage_add("user_name", "Alice")
        assert len(mg.staged) == 1
        commit = mg.commit("Add user name")
        assert commit.message == "Add user name"
        assert len(commit.diffs) == 1
        assert mg.state["user_name"] == "Alice"

    def test_commit_clears_staging(self, mg: MemoryGit) -> None:
        mg.stage_add("key", "value")
        mg.commit("Add key")
        assert mg.staged == []

    def test_empty_commit(self, mg: MemoryGit) -> None:
        commit = mg.commit("Nothing to do")
        assert commit is not None
        assert commit.diffs == []

    def test_multiple_diffs_in_commit(self, mg: MemoryGit) -> None:
        mg.stage_add("a", "1")
        mg.stage_add("b", "2")
        mg.stage_delete("c", "old")
        commit = mg.commit("Multi diff")
        assert len(commit.diffs) == 3

    def test_commit_chain(self, mg: MemoryGit) -> None:
        c1 = mg.commit("First", [MemoryDiff("add", "x", new_value="1")])
        c2 = mg.commit("Second", [MemoryDiff("add", "y", new_value="2")])
        assert c2.parent_hash == c1.hash
        assert c1.parent_hash is not None  # initial commit


class TestBranching:
    def test_create_branch(self, mg: MemoryGit) -> None:
        mg.commit("Add", [MemoryDiff("add", "k", new_value="v")])
        branch = mg.branch("experiment")
        assert branch.name == "experiment"
        assert branch.head == mg.head
        assert len(mg.list_branches()) == 2

    def test_branch_duplicate_raises(self, mg: MemoryGit) -> None:
        mg.branch("feat")
        with pytest.raises(ValueError, match="already exists"):
            mg.branch("feat")

    def test_checkout_switch(self, mg: MemoryGit) -> None:
        mg.commit("Add a", [MemoryDiff("add", "a", new_value="1")])
        mg.branch("experiment")
        mg.checkout("experiment")
        assert mg.current_branch == "experiment"
        mg.commit("Add b", [MemoryDiff("add", "b", new_value="2")])
        assert "b" in mg.state
        assert "a" in mg.state

    def test_branch_isolation(self, mg: MemoryGit) -> None:
        mg.commit("Add a", [MemoryDiff("add", "a", new_value="1")])
        mg.branch("experiment")
        mg.checkout("experiment")
        mg.commit("Add exp", [MemoryDiff("add", "exp", new_value="yes")])
        mg.checkout("main")
        assert "exp" not in mg.state
        assert "a" in mg.state

    def test_checkout_nonexistent_raises(self, mg: MemoryGit) -> None:
        with pytest.raises(KeyError):
            mg.checkout("nonexistent")


class TestMerge:
    def test_merge_branch(self, mg: MemoryGit) -> None:
        mg.commit("Base", [MemoryDiff("add", "base", new_value="b")])
        mg.branch("feature")
        mg.checkout("feature")
        mg.commit("Feature", [MemoryDiff("add", "feat", new_value="f")])
        mg.checkout("main")
        result = mg.merge("feature")
        assert "feat" in mg.state
        assert "merge" in result.message.lower() or "Merge" in result.message

    def test_merge_no_new_commits(self, mg: MemoryGit) -> None:
        mg.commit("Base", [MemoryDiff("add", "k", new_value="v")])
        mg.branch("same")
        result = mg.merge("same")
        assert result.hash == mg.head  # no new commit


class TestDiff:
    def test_diff_between_branches(self, mg: MemoryGit) -> None:
        mg.commit("Add a", [MemoryDiff("add", "a", new_value="1")])
        mg.branch("exp")
        mg.checkout("exp")
        mg.commit("Add b", [MemoryDiff("add", "b", new_value="2")])
        mg.commit("Modify a", [MemoryDiff("modify", "a", old_value="1", new_value="3")])
        mg.checkout("main")
        diffs = mg.diff("main", "exp")
        ops = {d.op for d in diffs}
        assert "add" in ops
        assert "modify" in ops

    def test_diff_by_commit_hash(self, mg: MemoryGit) -> None:
        c1 = mg.commit("Add x", [MemoryDiff("add", "x", new_value="1")])
        c2 = mg.commit("Update x", [MemoryDiff("modify", "x", old_value="1", new_value="2")])
        diffs = mg.diff(c1.hash, c2.hash)
        assert len(diffs) == 1
        assert diffs[0].op == "modify"


class TestRollback:
    def test_rollback_reverts_changes(self, mg: MemoryGit) -> None:
        c1 = mg.commit("Add a", [MemoryDiff("add", "a", new_value="1")])
        mg.commit("Add b", [MemoryDiff("add", "b", new_value="2")])
        assert "b" in mg.state
        result = mg.rollback(c1.hash)
        assert "b" not in mg.state
        assert "a" in mg.state
        assert result.author == "rollback"

    def test_rollback_to_current_noop(self, mg: MemoryGit) -> None:
        c1 = mg.commit("Add a", [MemoryDiff("add", "a", new_value="1")])
        result = mg.rollback(c1.hash)
        assert "a" in mg.state


class TestLog:
    def test_log_limit(self, mg: MemoryGit) -> None:
        for i in range(10):
            mg.commit(f"Commit {i}", [MemoryDiff("add", f"k{i}", new_value=str(i))])
        log = mg.log(limit=5)
        assert len(log) == 5
        assert log[0].message == "Commit 9"

    def test_log_shows_newest_first(self, mg: MemoryGit) -> None:
        mg.commit("First", [MemoryDiff("add", "a", new_value="1")])
        mg.commit("Second", [MemoryDiff("add", "b", new_value="2")])
        log = mg.log()
        assert log[0].message == "Second"
        assert log[1].message == "First"


class TestRendering:
    def test_render_log(self, mg: MemoryGit) -> None:
        mg.commit("Test commit", [MemoryDiff("add", "x", new_value="y")])
        output = mg.render_log()
        assert "Test commit" in output
        assert "main" in output

    def test_commit_summary(self, mg: MemoryGit) -> None:
        c = mg.commit(
            "Multi",
            [
                MemoryDiff("add", "a", new_value="1"),
                MemoryDiff("modify", "b", old_value="2", new_value="3"),
                MemoryDiff("delete", "c", old_value="4"),
            ],
        )
        summary = c.summary()
        assert "+1" in summary
        assert "~1" in summary
        assert "-1" in summary
