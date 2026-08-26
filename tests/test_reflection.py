"""Tests for the Reflection Engine."""

from __future__ import annotations

import pytest

from hermes_tui.reflection import (
    ReflectionEngine,
    ReflectionResult,
    TaskOutcome,
)
from hermes_tui.skill_forge import ProposalStatus, ProposalType, SkillForge
from hermes_tui.thought_graph import NodeKind, ThoughtGraph


@pytest.fixture()
def forge() -> SkillForge:
    return SkillForge()


@pytest.fixture()
def graph() -> ThoughtGraph:
    return ThoughtGraph()


@pytest.fixture()
def engine(forge: SkillForge, graph: ThoughtGraph) -> ReflectionEngine:
    return ReflectionEngine(forge, graph)


class TestHeuristicReflection:
    def test_failed_task_creates_antipattern(
        self, engine: ReflectionEngine
    ) -> None:
        outcome = TaskOutcome(
            description="Search for a file",
            success=False,
            errors_encountered=["FileNotFoundError: missing.txt"],
            conversation_excerpt="User: find the file\nAgent: error...",
        )
        import asyncio

        result = asyncio.new_event_loop().run_until_complete(engine.reflect(outcome))
        assert any(i.category == "antipattern" for i in result.insights)
        assert any("FileNotFoundError" in i.description for i in result.insights)

    def test_successful_tools_creates_pattern(
        self, engine: ReflectionEngine
    ) -> None:
        outcome = TaskOutcome(
            description="Search the web",
            success=True,
            tools_used=["web_search", "read_file"],
        )
        import asyncio

        result = asyncio.new_event_loop().run_until_complete(engine.reflect(outcome))
        assert any(i.category == "pattern" for i in result.insights)

    def test_positive_user_feedback(
        self, engine: ReflectionEngine
    ) -> None:
        outcome = TaskOutcome(
            description="Write code",
            success=True,
            user_feedback="Thanks, great work!",
        )
        import asyncio

        result = asyncio.new_event_loop().run_until_complete(engine.reflect(outcome))
        assert len(result.insights) > 0

    def test_empty_outcome(
        self, engine: ReflectionEngine
    ) -> None:
        outcome = TaskOutcome(description="Nothing", success=True)
        import asyncio

        result = asyncio.new_event_loop().run_until_complete(engine.reflect(outcome))
        assert isinstance(result, ReflectionResult)


class TestLLMReflection:
    @pytest.mark.asyncio
    async def test_llm_reflection_parses_json(
        self, forge: SkillForge, graph: ThoughtGraph
    ) -> None:
        async def mock_llm(prompt: str, **kwargs: object) -> str:
            return '''
            {
              "self_assessment": "I did well on this task.",
              "insights": [
                {
                  "category": "pattern",
                  "description": "Using structured output helped",
                  "evidence": "The JSON response was parsed correctly",
                  "confidence": 0.9,
                  "affected_skill": null
                }
              ],
              "proposed_changes": [
                {
                  "type": "new_skill",
                  "target_skill": null,
                  "title": "Structured output skill",
                  "rationale": "JSON output is reusable",
                  "draft_content": "# Structured Output\\n..."
                }
              ],
              "confidence": 0.85
            }
            '''

        engine = ReflectionEngine(forge, graph, llm=mock_llm)
        outcome = TaskOutcome(description="Test", success=True)
        result = await engine.reflect(outcome)

        assert result.confidence == 0.85
        assert len(result.insights) == 1
        assert result.insights[0].category == "pattern"
        assert len(result.proposed_skill_changes) == 1
        assert result.proposed_skill_changes[0]["title"] == "Structured output skill"

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_heuristic(
        self, forge: SkillForge, graph: ThoughtGraph
    ) -> None:
        async def bad_llm(prompt: str, **kwargs: object) -> str:
            return "not valid json at all"

        engine = ReflectionEngine(forge, graph, llm=bad_llm)
        outcome = TaskOutcome(
            description="Test",
            success=False,
            errors_encountered=["some error"],
        )
        result = await engine.reflect(outcome)
        # Should fall back to heuristic, which produces antipattern on error.
        assert len(result.insights) > 0

    @pytest.mark.asyncio
    async def test_high_confidence_creates_proposal(
        self, forge: SkillForge, graph: ThoughtGraph
    ) -> None:
        async def mock_llm(prompt: str, **kwargs: object) -> str:
            return '''
            {
              "self_assessment": "Good",
              "insights": [
                {"category": "shortcut", "description": "A shortcut", "evidence": "", "confidence": 0.95}
              ],
              "proposed_changes": [
                {
                  "type": "new_skill",
                  "target_skill": null,
                  "title": "Shortcut skill",
                  "rationale": "Useful",
                  "draft_content": "# Skill",
                  "confidence": 0.9
                }
              ],
              "confidence": 0.9
            }
            '''

        engine = ReflectionEngine(forge, graph, llm=mock_llm)
        outcome = TaskOutcome(description="Test", success=True)
        await engine.reflect(outcome)

        pending = forge.pending_reviews()
        assert len(pending) >= 1
        assert any("Shortcut skill" in p.title for p in pending)


class TestThoughtGraphIntegration:
    @pytest.mark.asyncio
    async def test_reflection_adds_graph_nodes(
        self, forge: SkillForge, graph: ThoughtGraph
    ) -> None:
        engine = ReflectionEngine(forge, graph)
        outcome = TaskOutcome(description="Test", success=True)
        await engine.reflect(outcome)
        reflections = graph.filter_by_kind(NodeKind.REFLECTION)
        assert len(reflections) >= 1


class TestHistory:
    def test_history_accumulates(
        self, engine: ReflectionEngine
    ) -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        for i in range(3):
            outcome = TaskOutcome(description=f"Task {i}", success=True)
            loop.run_until_complete(engine.reflect(outcome))
        assert len(engine.history) == 3

    def test_render_history(self, engine: ReflectionEngine) -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        outcome = TaskOutcome(description="Render test", success=True)
        loop.run_until_complete(engine.reflect(outcome))
        output = engine.render_history()
        assert "Reflection History" in output

    def test_render_empty_history(self, engine: ReflectionEngine) -> None:
        output = engine.render_history()
        assert "No reflections yet" in output
