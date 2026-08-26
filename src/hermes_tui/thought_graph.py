"""
Thought Graph — non-linear reasoning visualization.

Instead of treating the agent's reasoning as a flat chat log, the Thought
Graph records every cognitive step (LLM call, tool execution, memory
recall, skill activation, reflection) as a node in a directed graph.
Edges represent causal/temporal flow.  The TUI renders this graph with
ASCII connectors so users can see *how* the agent reached a conclusion,
expand/collapse branches, and inspect intermediate state.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NodeKind(str, Enum):
    """Categorisation of a reasoning node."""

    USER_INPUT = "user_input"
    LLM_THINK = "llm_think"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MEMORY_RECALL = "memory_recall"
    MEMORY_STORE = "memory_store"
    SKILL_MATCH = "skill_match"
    SKILL_LOAD = "skill_load"
    REFLECTION = "reflection"
    SKILL_PROPOSAL = "skill_proposal"
    COMPRESSION = "compression"
    ERROR = "error"
    BRANCH = "branch"
    MERGE = "merge"


@dataclass
class ThoughtNode:
    """A single node in the thought graph.

    Attributes:
        id: Unique node identifier.
        kind: What kind of cognitive step this represents.
        label: Short human-readable summary.
        detail: Full content / payload (can be large; collapsed by default).
        parent_id: The node that led to this one.
        timestamp: When the node was created (monotonic).
        metadata: Arbitrary structured data (token counts, tool args, etc.).
        collapsed: Whether the TUI should render this node collapsed.
        tags: Free-form tags for filtering / colour-coding.
    """

    id: str
    kind: NodeKind
    label: str
    detail: str = ""
    parent_id: str | None = None
    timestamp: float = field(default_factory=time.monotonic)
    metadata: dict[str, Any] = field(default_factory=dict)
    collapsed: bool = False
    tags: list[str] = field(default_factory=list)
    _children: list[str] = field(default_factory=list, repr=False)

    @property
    def is_terminal(self) -> bool:
        """Return True if this node has no children."""
        return len(self._children) == 0

    def word_count(self) -> int:
        """Approximate word count of detail text."""
        return len(self.detail.split()) if self.detail else 0


@dataclass
class GraphStats:
    """Aggregate statistics for a thought graph session."""

    total_nodes: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    memories_recalled: int = 0
    memories_stored: int = 0
    skills_activated: int = 0
    reflections: int = 0
    errors: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    duration_ms: float = 0.0


class ThoughtGraph:
    """Directed graph of the agent's reasoning process.

    The graph is append-only during a session; nodes are never removed.
    Branches occur when a tool call produces multiple downstream effects,
    or when the agent explores alternative approaches.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ThoughtNode] = {}
        self._roots: list[str] = []
        self._leaf_ids: set[str] = set()
        self._counter: int = 0
        self._start_time: float = time.monotonic()
        self._active_branch: str | None = None

    def _next_id(self) -> str:
        self._counter += 1
        return f"n{self._counter:04d}"

    def add_node(
        self,
        kind: NodeKind,
        label: str,
        detail: str = "",
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        collapsed: bool = False,
    ) -> ThoughtNode:
        """Add a node to the graph.

        Args:
            kind: The type of cognitive step.
            label: Short summary.
            detail: Full content.
            parent_id: Parent node; if None, this is a root node.
            metadata: Structured data.
            tags: Filtering tags.
            collapsed: Initial collapsed state.

        Returns:
            The created :class:`ThoughtNode`.
        """
        node_id = self._next_id()
        node = ThoughtNode(
            id=node_id,
            kind=kind,
            label=label,
            detail=detail,
            parent_id=parent_id,
            metadata=metadata or {},
            tags=tags or [],
            collapsed=collapsed,
        )
        self._nodes[node_id] = node

        if parent_id and parent_id in self._nodes:
            self._nodes[parent_id]._children.append(node_id)
            self._leaf_ids.discard(parent_id)
        else:
            self._roots.append(node_id)

        self._leaf_ids.add(node_id)
        self._active_branch = node_id
        logger.debug("ThoughtGraph +%s [%s] %s", node_id, kind.value, label[:60])
        return node

    def branch(
        self,
        kind: NodeKind,
        label: str,
        detail: str = "",
        from_node: str | None = None,
        **kwargs: Any,
    ) -> ThoughtNode:
        """Create an explicit branch point.

        Args:
            kind: Node kind for the branch marker.
            label: Branch description.
            detail: Full content.
            from_node: Node to branch from; defaults to active branch.
            **kwargs: Forwarded to :meth:`add_node`.

        Returns:
            The branch node.
        """
        parent = from_node or self._active_branch
        node = self.add_node(kind, label, detail, parent_id=parent, **kwargs)
        self._active_branch = node.id
        return node

    def get(self, node_id: str) -> ThoughtNode | None:
        """Return a node by ID, or None."""
        return self._nodes.get(node_id)

    @property
    def roots(self) -> list[ThoughtNode]:
        """Return all root nodes."""
        return [self._nodes[rid] for rid in self._roots if rid in self._nodes]

    @property
    def leaves(self) -> list[ThoughtNode]:
        """Return all current leaf nodes."""
        return [self._nodes[lid] for lid in self._leaf_ids if lid in self._nodes]

    @property
    def active_node(self) -> ThoughtNode | None:
        """Return the most recently added node on the active branch."""
        if self._active_branch:
            return self._nodes.get(self._active_branch)
        return None

    def children(self, node_id: str) -> list[ThoughtNode]:
        """Return direct children of a node."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._nodes[cid] for cid in node._children if cid in self._nodes]

    def path_to_root(self, node_id: str) -> list[ThoughtNode]:
        """Return the chain from *node_id* up to its root."""
        chain: list[ThoughtNode] = []
        current = self._nodes.get(node_id)
        seen: set[str] = set()
        while current and current.id not in seen:
            chain.append(current)
            seen.add(current.id)
            if current.parent_id:
                current = self._nodes.get(current.parent_id)
            else:
                break
        return list(reversed(chain))

    def walk(self) -> list[ThoughtNode]:
        """Return all nodes in BFS order."""
        result: list[ThoughtNode] = []
        queue = list(self.roots)
        seen: set[str] = set()
        while queue:
            node = queue.pop(0)
            if node.id in seen:
                continue
            seen.add(node.id)
            result.append(node)
            queue.extend(self.children(node.id))
        return result

    def filter_by_kind(self, kind: NodeKind) -> list[ThoughtNode]:
        """Return all nodes of a given kind."""
        return [n for n in self._nodes.values() if n.kind == kind]

    def filter_by_tag(self, tag: str) -> list[ThoughtNode]:
        """Return all nodes carrying a specific tag."""
        return [n for n in self._nodes.values() if tag in n.tags]

    def stats(self) -> GraphStats:
        """Compute aggregate statistics for the graph."""
        s = GraphStats(total_nodes=len(self._nodes))
        s.duration_ms = (time.monotonic() - self._start_time) * 1000
        for node in self._nodes.values():
            if node.kind == NodeKind.LLM_THINK or node.kind == NodeKind.LLM_RESPONSE:
                s.llm_calls += 1
            elif node.kind == NodeKind.TOOL_CALL:
                s.tool_calls += 1
            elif node.kind == NodeKind.MEMORY_RECALL:
                s.memories_recalled += 1
            elif node.kind == NodeKind.MEMORY_STORE:
                s.memories_stored += 1
            elif node.kind == NodeKind.SKILL_MATCH or node.kind == NodeKind.SKILL_LOAD:
                s.skills_activated += 1
            elif node.kind == NodeKind.REFLECTION:
                s.reflections += 1
            elif node.kind == NodeKind.ERROR:
                s.errors += 1
            s.total_tokens_in += node.metadata.get("tokens_in", 0)
            s.total_tokens_out += node.metadata.get("tokens_out", 0)
        return s

    def render_tree(self, max_depth: int = 3) -> str:
        """Render the graph as an ASCII tree for terminal display.

        Args:
            max_depth: Maximum depth to render (collapsed nodes are
                truncated but shown with a ``…`` marker).

        Returns:
            Multi-line ASCII tree string.
        """
        kind_icons = {
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
            NodeKind.COMPRESSION: "🗜️",
            NodeKind.ERROR: "❌",
            NodeKind.BRANCH: "🌿",
            NodeKind.MERGE: "🔀",
        }
        lines: list[str] = []

        def _render(node: ThoughtNode, prefix: str, depth: int) -> None:
            icon = kind_icons.get(node.kind, "•")
            label = node.label[:70]
            if node.collapsed or (depth >= max_depth and not node.is_terminal):
                child_count = len(node._children)
                suffix = f" …(+{child_count})" if child_count else ""
                lines.append(f"{prefix}{icon} {label}{suffix}")
                return
            lines.append(f"{prefix}{icon} {label}")
            childs = self.children(node.id)
            for i, child in enumerate(childs):
                is_last = i == len(childs) - 1
                connector = "└── " if is_last else "├── "
                _render(child, prefix + connector, depth + 1)
                if not is_last:
                    # We already draw the connector in _render, but need
                    # the vertical line for subsequent children.
                    pass

        for root in self.roots:
            _render(root, "", 0)

        return "\n".join(lines)

    def clear(self) -> None:
        """Reset the graph (start a new session)."""
        self._nodes.clear()
        self._roots.clear()
        self._leaf_ids.clear()
        self._counter = 0
        self._start_time = time.monotonic()
        self._active_branch = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a plain dict."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "kind": n.kind.value,
                    "label": n.label,
                    "detail": n.detail,
                    "parent_id": n.parent_id,
                    "timestamp": n.timestamp,
                    "metadata": n.metadata,
                    "tags": n.tags,
                    "collapsed": n.collapsed,
                    "children": n._children,
                }
                for n in self._nodes.values()
            ],
            "roots": self._roots,
        }
