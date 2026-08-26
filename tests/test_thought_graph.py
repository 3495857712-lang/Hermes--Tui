"""Tests for the Thought Graph module."""

from __future__ import annotations

import pytest

from hermes_tui.thought_graph import NodeKind, ThoughtGraph, ThoughtNode


@pytest.fixture()
def graph() -> ThoughtGraph:
    return ThoughtGraph()


class TestNodeCreation:
    def test_add_root_node(self, graph: ThoughtGraph) -> None:
        node = graph.add_node(NodeKind.USER_INPUT, "Hello")
        assert node.id == "n0001"
        assert node.kind == NodeKind.USER_INPUT
        assert node.label == "Hello"
        assert node.parent_id is None

    def test_add_child_node(self, graph: ThoughtGraph) -> None:
        root = graph.add_node(NodeKind.USER_INPUT, "Root")
        child = graph.add_node(NodeKind.LLM_THINK, "Thinking", parent_id=root.id)
        assert child.parent_id == root.id
        assert root._children == [child.id]

    def test_node_ids_increment(self, graph: ThoughtGraph) -> None:
        n1 = graph.add_node(NodeKind.USER_INPUT, "1")
        n2 = graph.add_node(NodeKind.USER_INPUT, "2")
        n3 = graph.add_node(NodeKind.USER_INPUT, "3")
        assert n1.id == "n0001"
        assert n2.id == "n0002"
        assert n3.id == "n0003"

    def test_node_metadata(self, graph: ThoughtGraph) -> None:
        node = graph.add_node(
            NodeKind.TOOL_CALL,
            "web_search",
            metadata={"tokens": 100, "args": {"q": "test"}},
            tags=["search", "web"],
        )
        assert node.metadata["tokens"] == 100
        assert "search" in node.tags


class TestGraphTraversal:
    def test_roots(self, graph: ThoughtGraph) -> None:
        r1 = graph.add_node(NodeKind.USER_INPUT, "R1")
        r2 = graph.add_node(NodeKind.USER_INPUT, "R2")
        roots = graph.roots
        assert len(roots) == 2
        assert r1 in roots
        assert r2 in roots

    def test_children(self, graph: ThoughtGraph) -> None:
        root = graph.add_node(NodeKind.USER_INPUT, "Root")
        c1 = graph.add_node(NodeKind.LLM_THINK, "C1", parent_id=root.id)
        c2 = graph.add_node(NodeKind.TOOL_CALL, "C2", parent_id=root.id)
        children = graph.children(root.id)
        assert len(children) == 2
        assert c1 in children
        assert c2 in children

    def test_path_to_root(self, graph: ThoughtGraph) -> None:
        r = graph.add_node(NodeKind.USER_INPUT, "R")
        c = graph.add_node(NodeKind.LLM_THINK, "C", parent_id=r.id)
        gc = graph.add_node(NodeKind.TOOL_CALL, "GC", parent_id=c.id)
        path = graph.path_to_root(gc.id)
        assert [n.id for n in path] == [r.id, c.id, gc.id]

    def test_walk_bfs(self, graph: ThoughtGraph) -> None:
        r = graph.add_node(NodeKind.USER_INPUT, "R")
        c1 = graph.add_node(NodeKind.LLM_THINK, "C1", parent_id=r.id)
        c2 = graph.add_node(NodeKind.LLM_THINK, "C2", parent_id=r.id)
        gc1 = graph.add_node(NodeKind.TOOL_CALL, "GC1", parent_id=c1.id)
        walked = graph.walk()
        assert walked[0].id == r.id
        assert walked[1].id == c1.id
        assert walked[2].id == c2.id
        assert walked[3].id == gc1.id

    def test_leaves(self, graph: ThoughtGraph) -> None:
        r = graph.add_node(NodeKind.USER_INPUT, "R")
        c1 = graph.add_node(NodeKind.LLM_THINK, "C1", parent_id=r.id)
        graph.add_node(NodeKind.TOOL_CALL, "C2", parent_id=r.id)
        # c1 should no longer be a leaf after child added? No - c1 has no children.
        leaves = graph.leaves
        leaf_ids = {n.id for n in leaves}
        assert c1.id in leaf_ids  # c1 is still a leaf


class TestBranching:
    def test_branch_creates_marker(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "Root")
        branch = graph.branch(NodeKind.BRANCH, "Try approach A")
        assert branch.kind == NodeKind.BRANCH
        assert graph.active_node.id == branch.id

    def test_active_branch_tracks_latest(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "R")
        graph.add_node(NodeKind.LLM_THINK, "T1")
        graph.add_node(NodeKind.TOOL_CALL, "T2")
        assert graph.active_node.label == "T2"


class TestFiltering:
    def test_filter_by_kind(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "U1")
        graph.add_node(NodeKind.LLM_THINK, "T1")
        graph.add_node(NodeKind.LLM_THINK, "T2")
        graph.add_node(NodeKind.TOOL_CALL, "TC1")
        thinks = graph.filter_by_kind(NodeKind.LLM_THINK)
        assert len(thinks) == 2

    def test_filter_by_tag(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "U1", tags=["important"])
        graph.add_node(NodeKind.USER_INPUT, "U2", tags=["casual"])
        graph.add_node(NodeKind.USER_INPUT, "U3", tags=["important", "urgent"])
        important = graph.filter_by_tag("important")
        assert len(important) == 2


class TestStats:
    def test_empty_stats(self, graph: ThoughtGraph) -> None:
        stats = graph.stats()
        assert stats.total_nodes == 0
        assert stats.llm_calls == 0

    def test_stats_counts(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "U")
        graph.add_node(NodeKind.LLM_THINK, "T1")
        graph.add_node(NodeKind.LLM_RESPONSE, "R1")
        graph.add_node(NodeKind.TOOL_CALL, "TC")
        graph.add_node(NodeKind.MEMORY_RECALL, "M")
        graph.add_node(NodeKind.REFLECTION, "Ref")
        graph.add_node(NodeKind.ERROR, "E")
        stats = graph.stats()
        assert stats.total_nodes == 7
        assert stats.llm_calls == 2  # think + response
        assert stats.tool_calls == 1
        assert stats.memories_recalled == 1
        assert stats.reflections == 1
        assert stats.errors == 1

    def test_token_tracking(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.LLM_THINK, "T", metadata={"tokens_in": 100, "tokens_out": 50})
        stats = graph.stats()
        assert stats.total_tokens_in == 100
        assert stats.total_tokens_out == 50


class TestRendering:
    def test_render_tree_empty(self, graph: ThoughtGraph) -> None:
        tree = graph.render_tree()
        assert tree == ""

    def test_render_tree_single(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "Hello world")
        tree = graph.render_tree()
        assert "Hello world" in tree

    def test_render_tree_nested(self, graph: ThoughtGraph) -> None:
        r = graph.add_node(NodeKind.USER_INPUT, "Root")
        graph.add_node(NodeKind.LLM_THINK, "Child", parent_id=r.id)
        tree = graph.render_tree()
        assert "├──" in tree or "└──" in tree

    def test_render_tree_collapsed(self, graph: ThoughtGraph) -> None:
        r = graph.add_node(NodeKind.USER_INPUT, "Root")
        child = graph.add_node(NodeKind.LLM_THINK, "Child", parent_id=r.id)
        graph.add_node(NodeKind.TOOL_CALL, "Grandchild", parent_id=child.id)
        child.collapsed = True
        tree = graph.render_tree(max_depth=1)
        assert "…" in tree or "(+" in tree


class TestClear:
    def test_clear_resets(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "Hello")
        graph.add_node(NodeKind.LLM_THINK, "Thinking")
        graph.clear()
        assert len(graph.walk()) == 0
        assert graph.roots == []
        assert graph.active_node is None

    def test_clear_resets_counter(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "A")
        graph.clear()
        node = graph.add_node(NodeKind.USER_INPUT, "B")
        assert node.id == "n0001"


class TestSerialization:
    def test_to_dict(self, graph: ThoughtGraph) -> None:
        graph.add_node(NodeKind.USER_INPUT, "Hello")
        data = graph.to_dict()
        assert "nodes" in data
        assert "roots" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["kind"] == "user_input"
