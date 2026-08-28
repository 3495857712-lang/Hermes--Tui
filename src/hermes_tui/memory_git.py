"""
Memory Git — version-controlled memory with diff, branch, and rollback.

Treats the agent's long-term memory like a Git repository.  Every memory
mutation (add, update, delete, extract) creates an immutable commit with
a parent hash.  Users can inspect the diff between any two commits,
create branches to experiment with different memory states, and roll
back to any previous commit.

This is fundamentally different from append-only memory logs: it gives
the agent *auditable, reversible memory evolution*.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def _hash(content: str) -> str:
    """Compute a short SHA-256 hash."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


class MemoryOpType(str):
    """Memory mutation operation types."""

    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    EXTRACT = "extract"
    MERGE = "merge"
    PRUNE = "prune"
    IMPORT = "import"
    RESET = "reset"


@dataclass
class MemoryDiff:
    """A single line-item change between two memory states."""

    op: str  # add / modify / delete
    key: str
    old_value: str | None = None
    new_value: str | None = None
    layer: str = ""

    def render(self) -> str:
        """Render as a unified-diff-style line."""
        if self.op == "add":
            return f"+ [{self.layer}] {self.key}: {self.new_value}"
        if self.op == "delete":
            return f"- [{self.layer}] {self.key}: {self.old_value}"
        return f"~ [{self.layer}] {self.key}:\n    - {self.old_value}\n    + {self.new_value}"


@dataclass
class MemoryCommit:
    """An immutable snapshot of memory mutations.

    Attributes:
        hash: Unique commit hash.
        parent_hash: Hash of the previous commit (None for initial).
        message: Human-readable commit message.
        timestamp: When the commit was created.
        diffs: List of changes in this commit.
        branch: Branch this commit belongs to.
        author: Who created this commit (agent / user / system).
        tags: Arbitrary tags for categorisation.
    """

    hash: str
    parent_hash: str | None
    message: str
    timestamp: datetime
    diffs: list[MemoryDiff] = field(default_factory=list)
    branch: str = "main"
    author: str = "agent"
    tags: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line commit summary."""
        adds = sum(1 for d in self.diffs if d.op == "add")
        mods = sum(1 for d in self.diffs if d.op == "modify")
        dels = sum(1 for d in self.diffs if d.op == "delete")
        parts = []
        if adds:
            parts.append(f"+{adds}")
        if mods:
            parts.append(f"~{mods}")
        if dels:
            parts.append(f"-{dels}")
        stats = ", ".join(parts) if parts else "no changes"
        return f"[{self.hash[:8]}] ({self.branch}) {self.message} — {stats}"


class MemoryBranch:
    """A named pointer to a commit hash."""

    def __init__(self, name: str, head: str | None = None) -> None:
        self.name = name
        self.head = head
        self.created_at = datetime.now(UTC)


class MemoryGit:
    """Version-controlled memory store with Git-like semantics.

    Usage::

        mg = MemoryGit()
        mg.commit("Initial memory", [MemoryDiff("add", "user_name", new_value="Alice")])
        mg.branch("experiment")
        mg.checkout("experiment")
        mg.commit("Try new memory", [...])
        mg.diff("main", "experiment")
        mg.checkout("main")
        mg.merge("experiment")
    """

    def __init__(self) -> None:
        self._commits: dict[str, MemoryCommit] = {}
        self._branches: dict[str, MemoryBranch] = {}
        self._current_branch: str = "main"
        self._head: str | None = None
        self._staged: list[MemoryDiff] = []
        self._state: dict[str, str] = {}  # key → value snapshot

        # Create initial empty commit.
        self._branches["main"] = MemoryBranch("main")
        initial = self._create_commit("Initial empty memory", [], author="system")
        self._head = initial.hash
        self._branches["main"].head = initial.hash

    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------
    def stage(self, diff: MemoryDiff) -> None:
        """Stage a memory change for the next commit."""
        self._staged.append(diff)

    def stage_add(self, key: str, value: str, layer: str = "episodic") -> None:
        """Stage an addition."""
        self._staged.append(MemoryDiff("add", key, new_value=value, layer=layer))

    def stage_update(self, key: str, old: str, new: str, layer: str = "episodic") -> None:
        """Stage a modification."""
        self._staged.append(MemoryDiff("modify", key, old_value=old, new_value=new, layer=layer))

    def stage_delete(self, key: str, old: str, layer: str = "episodic") -> None:
        """Stage a deletion."""
        self._staged.append(MemoryDiff("delete", key, old_value=old, layer=layer))

    @property
    def staged(self) -> list[MemoryDiff]:
        """Return currently staged diffs."""
        return list(self._staged)

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------
    def _create_commit(
        self,
        message: str,
        diffs: list[MemoryDiff],
        author: str = "agent",
        branch: str | None = None,
    ) -> MemoryCommit:
        """Internal: create and store a commit."""
        content = json.dumps(
            {
                "parent": self._head,
                "message": message,
                "diffs": [d.__dict__ for d in diffs],
                "timestamp": datetime.now(UTC).isoformat(),
            },
            sort_keys=True,
            default=str,
        )
        commit_hash = _hash(content)
        commit = MemoryCommit(
            hash=commit_hash,
            parent_hash=self._head,
            message=message,
            timestamp=datetime.now(UTC),
            diffs=diffs,
            branch=branch or self._current_branch,
            author=author,
        )
        self._commits[commit_hash] = commit
        return commit

    def commit(
        self,
        message: str,
        diffs: list[MemoryDiff] | None = None,
        author: str = "agent",
    ) -> MemoryCommit:
        """Create a commit with staged (or provided) diffs.

        Args:
            message: Commit message.
            diffs: Optional explicit diffs; otherwise staged diffs are used.
            author: Commit author.

        Returns:
            The created :class:`MemoryCommit`.
        """
        all_diffs = diffs if diffs is not None else list(self._staged)
        if not all_diffs:
            logger.debug("Empty commit attempted: %s", message)

        commit = self._create_commit(message, all_diffs, author=author)
        self._head = commit.hash
        self._branches[self._current_branch].head = commit.hash

        # Apply diffs to current state.
        for d in all_diffs:
            if d.op == "add" or d.op == "modify":
                self._state[d.key] = d.new_value or ""
            elif d.op == "delete":
                self._state.pop(d.key, None)

        self._staged.clear()
        logger.info("Memory commit %s: %s", commit.hash[:8], message)
        return commit

    # ------------------------------------------------------------------
    # Branching
    # ------------------------------------------------------------------
    def branch(self, name: str) -> MemoryBranch:
        """Create a new branch at the current HEAD.

        Args:
            name: Branch name.

        Returns:
            The new branch.

        Raises:
            ValueError: If the branch already exists.
        """
        if name in self._branches:
            raise ValueError(f"Branch '{name}' already exists")
        b = MemoryBranch(name, head=self._head)
        self._branches[name] = b
        logger.info("Created branch '%s' at %s", name, self._head)
        return b

    def checkout(self, name: str) -> MemoryCommit:
        """Switch to a branch.

        Args:
            name: Branch name.

        Returns:
            The HEAD commit of the branch.

        Raises:
            KeyError: If the branch doesn't exist.
        """
        if name not in self._branches:
            raise KeyError(f"Branch '{name}' not found")
        self._current_branch = name
        self._head = self._branches[name].head
        self._rebuild_state()
        self._staged.clear()
        logger.info("Switched to branch '%s' at %s", name, self._head)
        return self._commits[self._head]  # type: ignore[index]

    def merge(self, branch_name: str, message: str | None = None) -> MemoryCommit:
        """Merge another branch into the current branch.

        This performs a simple replay-based merge: it walks the source
        branch's commits not in the current branch and applies their
        diffs.

        Args:
            branch_name: Branch to merge from.
            message: Merge commit message.

        Returns:
            The merge commit.
        """
        if branch_name not in self._branches:
            raise KeyError(f"Branch '{branch_name}' not found")
        source_head = self._branches[branch_name].head
        target_head = self._head

        # Find commits unique to source branch.
        source_commits = self._commits_between(target_head, source_head)
        if not source_commits:
            logger.info("Nothing to merge from '%s'", branch_name)
            return self._commits[target_head]  # type: ignore[index]

        merged_diffs: list[MemoryDiff] = []
        for c in reversed(source_commits):
            merged_diffs.extend(c.diffs)

        msg = message or f"Merge branch '{branch_name}' into {self._current_branch}"
        return self.commit(msg, merged_diffs, author="merge")

    def list_branches(self) -> list[tuple[str, str, bool]]:
        """Return (name, head_hash, is_current) for all branches."""
        return [
            (b.name, b.head or "", b.name == self._current_branch) for b in self._branches.values()
        ]

    # ------------------------------------------------------------------
    # Log & Diff
    # ------------------------------------------------------------------
    def log(self, limit: int = 20) -> list[MemoryCommit]:
        """Return commit history from current HEAD backwards."""
        result: list[MemoryCommit] = []
        current_hash = self._head
        while current_hash and len(result) < limit:
            commit = self._commits.get(current_hash)
            if not commit:
                break
            result.append(commit)
            current_hash = commit.parent_hash
        return result

    def diff(self, from_ref: str, to_ref: str) -> list[MemoryDiff]:
        """Compute the diff between two commits/branches.

        Args:
            from_ref: Commit hash or branch name (older).
            to_ref: Commit hash or branch name (newer).

        Returns:
            List of diffs between the two states.
        """
        from_hash = self._resolve_ref(from_ref)
        to_hash = self._resolve_ref(to_ref)

        from_state = self._state_at(from_hash)
        to_state = self._state_at(to_hash)

        diffs: list[MemoryDiff] = []
        all_keys = set(from_state) | set(to_state)
        for key in sorted(all_keys):
            old = from_state.get(key)
            new = to_state.get(key)
            if old is None and new is not None:
                diffs.append(MemoryDiff("add", key, new_value=new))
            elif old is not None and new is None:
                diffs.append(MemoryDiff("delete", key, old_value=old))
            elif old != new:
                diffs.append(MemoryDiff("modify", key, old_value=old, new_value=new))
        return diffs

    def show(self, commit_hash: str) -> MemoryCommit | None:
        """Show a specific commit."""
        return self._commits.get(commit_hash)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------
    def rollback(self, commit_hash: str) -> MemoryCommit:
        """Roll back memory to a previous commit (creates a revert commit).

        This does not delete history; it creates a new commit that
        reverses all changes made after the target commit.

        Args:
            commit_hash: The commit to roll back to.

        Returns:
            The revert commit.
        """
        if commit_hash not in self._commits:
            raise KeyError(f"Commit '{commit_hash}' not found")

        # Get all commits after target.
        commits_to_revert = self._commits_between(commit_hash, self._head)
        if not commits_to_revert:
            logger.info("Already at target commit")
            return self._commits[commit_hash]

        # Reverse the diffs.
        revert_diffs: list[MemoryDiff] = []
        for commit in commits_to_revert:
            for d in reversed(commit.diffs):
                if d.op == "add":
                    revert_diffs.append(
                        MemoryDiff("delete", d.key, old_value=d.new_value, layer=d.layer)
                    )
                elif d.op == "delete":
                    revert_diffs.append(
                        MemoryDiff("add", d.key, new_value=d.old_value, layer=d.layer)
                    )
                elif d.op == "modify":
                    revert_diffs.append(
                        MemoryDiff(
                            "modify",
                            d.key,
                            old_value=d.new_value,
                            new_value=d.old_value,
                            layer=d.layer,
                        )
                    )

        return self.commit(f"Revert to {commit_hash[:8]}", revert_diffs, author="rollback")

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------
    @property
    def state(self) -> dict[str, str]:
        """Return the current memory state (key → value)."""
        return dict(self._state)

    @property
    def head(self) -> str | None:
        """Current HEAD commit hash."""
        return self._head

    @property
    def current_branch(self) -> str:
        """Current branch name."""
        return self._current_branch

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _resolve_ref(self, ref: str) -> str:
        """Resolve a branch name or commit hash to a commit hash."""
        if ref in self._branches:
            return self._branches[ref].head  # type: ignore[return-value]
        if ref in self._commits:
            return ref
        # Try partial hash.
        matches = [h for h in self._commits if h.startswith(ref)]
        if len(matches) == 1:
            return matches[0]
        raise KeyError(f"Ambiguous or unknown ref: {ref}")

    def _commits_between(
        self, older_hash: str | None, newer_hash: str | None
    ) -> list[MemoryCommit]:
        """Return commits between two hashes (newer exclusive, in reverse
        chronological order)."""
        result: list[MemoryCommit] = []
        current = newer_hash
        while current and current != older_hash:
            commit = self._commits.get(current)
            if not commit:
                break
            result.append(commit)
            current = commit.parent_hash
        return result

    def _state_at(self, commit_hash: str | None) -> dict[str, str]:
        """Reconstruct memory state at a given commit by replaying diffs."""
        if not commit_hash:
            return {}
        commits: list[MemoryCommit] = []
        current: str | None = commit_hash
        while current:
            commit = self._commits.get(current)
            if not commit:
                break
            commits.append(commit)
            current = commit.parent_hash
        state: dict[str, str] = {}
        for commit in reversed(commits):
            for d in commit.diffs:
                if d.op in ("add", "modify"):
                    state[d.key] = d.new_value or ""
                elif d.op == "delete":
                    state.pop(d.key, None)
        return state

    def _rebuild_state(self) -> None:
        """Rebuild current state from HEAD history."""
        self._state = self._state_at(self._head)

    def render_log(self, limit: int = 15) -> str:
        """Render commit log as a Git-style ASCII graph."""
        commits = self.log(limit)
        lines: list[str] = []
        for i, c in enumerate(commits):
            marker = "●" if i == 0 else "│"
            if i > 0:
                lines.append("│")
            lines.append(f"{marker} [{c.hash[:8]}] {c.message}")
            adds = sum(1 for d in c.diffs if d.op == "add")
            mods = sum(1 for d in c.diffs if d.op == "modify")
            dels = sum(1 for d in c.diffs if d.op == "delete")
            stats = []
            if adds:
                stats.append(f"\033[32m+{adds}\033[0m")
            if mods:
                stats.append(f"\033[33m~{mods}\033[0m")
            if dels:
                stats.append(f"\033[31m-{dels}\033[0m")
            if stats:
                lines.append(f"│  {' '.join(stats)}  ({c.author}, {c.branch})")
        return "\n".join(lines)
