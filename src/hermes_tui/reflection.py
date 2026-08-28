"""
Reflection Engine — the self-improvement loop.

After every task (or when explicitly invoked via /reflect), the engine
analyses what happened and produces structured insights.  These insights
feed into the Skill Forge as proposals.

The reflection cycle follows Hermes Agent's Observe → Execute →
Reflect → Crystallize → Reuse loop, but with a key difference: every
step is recorded in the Thought Graph and Memory Git, making the
self-evolution process fully auditable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from .skill_forge import ProposalType, ReflectionInsight, SkillForge
from .thought_graph import NodeKind, ThoughtGraph

logger = logging.getLogger(__name__)


@dataclass
class TaskOutcome:
    """Summary of a completed task for reflection."""

    description: str
    success: bool
    duration_seconds: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    skills_activated: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)
    user_feedback: str = ""
    token_usage: int = 0
    conversation_excerpt: str = ""


@dataclass
class ReflectionResult:
    """Structured output from a reflection cycle."""

    insights: list[ReflectionInsight] = field(default_factory=list)
    proposed_skill_changes: list[dict[str, Any]] = field(default_factory=list)
    self_assessment: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_actionable_insights(self) -> bool:
        """Return True if there are insights worth proposing."""
        return any(i.confidence >= 0.6 for i in self.insights)


class LLMBackend(Protocol):
    """Protocol for the LLM callable used by the reflection engine."""

    async def __call__(self, prompt: str, **kwargs: Any) -> str: ...


class ReflectionEngine:
    """Runs post-task reflection and feeds insights into the Skill Forge.

    The engine does not directly modify skills.  It produces
    :class:`ReflectionResult` objects which the agent loop can review
    and, if approved, convert into Skill Forge proposals.
    """

    REFLECTION_PROMPT_TEMPLATE = """You are reflecting on a task you just completed as an AI agent.
Analyse the outcome honestly and identify actionable improvements.

## Task
{task_description}

## Outcome
- Success: {success}
- Duration: {duration:.1f}s
- Tools used: {tools}
- Skills activated: {skills}
- Errors: {errors}
- User feedback: {feedback}

## Key Exchange
{excerpt}

## Relevant Existing Skills
{skills_inventory}

## Instructions
1. Identify what worked well (patterns, shortcuts, effective strategies).
2. Identify what went wrong or could be improved (gaps, friction, errors).
3. Determine if there is a reusable procedure that should become a skill.
4. Determine if an existing skill needs updating.
5. Be specific and evidence-based — cite the actual exchange above.

Respond as JSON with this structure:
{{
  "self_assessment": "honest one-paragraph evaluation",
  "insights": [
    {{
      "category": "pattern|antipattern|shortcut|gap|improvement",
      "description": "specific observation",
      "evidence": "quote or reference from the task",
      "confidence": 0.0-1.0,
      "affected_skill": "skill name or null"
    }}
  ],
  "proposed_changes": [
    {{
      "type": "new_skill|modify_skill|add_reference|improve_description",
      "target_skill": "name or null",
      "title": "short title",
      "rationale": "why this change",
      "draft_content": "markdown draft of the skill/change"
    }}
  ],
  "confidence": 0.0-1.0
}}"""

    def __init__(
        self,
        forge: SkillForge,
        thought_graph: ThoughtGraph | None = None,
        llm: LLMBackend | None = None,
    ) -> None:
        self.forge = forge
        self.thought_graph = thought_graph
        self._llm = llm
        self._history: list[ReflectionResult] = []

    def set_llm(self, llm: LLMBackend) -> None:
        """Set or replace the LLM backend."""
        self._llm = llm

    async def reflect(
        self,
        outcome: TaskOutcome,
        existing_skills: list[dict[str, Any]] | None = None,
    ) -> ReflectionResult:
        """Run a reflection cycle on a completed task.

        Args:
            outcome: Task outcome summary.
            existing_skills: Current skill inventory for context.

        Returns:
            A :class:`ReflectionResult` with insights and proposals.
        """
        # Record the reflection in the thought graph (regardless of backend).
        if self.thought_graph:
            self.thought_graph.add_node(
                NodeKind.REFLECTION,
                f"Reflection: {outcome.description[:60]}",
                detail=f"success={outcome.success}, errors={len(outcome.errors_encountered)}",
                metadata={"success": outcome.success},
            )

        if self._llm is not None:
            prompt = self._build_prompt(outcome, existing_skills or [])
            try:
                response = await self._llm(prompt, temperature=0.3)
                result = self._parse_reflection(response, outcome)
            except Exception as exc:
                logger.warning("LLM reflection failed, falling back to heuristic: %s", exc)
                result = self._heuristic_reflect(outcome)
        else:
            result = self._heuristic_reflect(outcome)

        self._history.append(result)

        # Auto-create proposals for high-confidence changes.
        for change in result.proposed_skill_changes:
            if change.get("confidence", 0) >= 0.7 or result.confidence >= 0.7:
                self._create_proposal_from_change(change, result, outcome)

        # Record insights as skill-proposal nodes in the thought graph.
        if self.thought_graph and result.insights:
            self.thought_graph.add_node(
                NodeKind.SKILL_PROPOSAL,
                f"Reflection produced {len(result.insights)} insights",
                detail="\n".join(
                    f"- [{i.category}] {i.description} (conf: {i.confidence:.2f})"
                    for i in result.insights
                ),
                metadata={"insight_count": len(result.insights)},
            )

        logger.info(
            "Reflection complete: %d insights, %d proposed changes (conf=%.2f)",
            len(result.insights),
            len(result.proposed_skill_changes),
            result.confidence,
        )
        return result

    def _build_prompt(self, outcome: TaskOutcome, existing_skills: list[dict[str, Any]]) -> str:
        skills_text = (
            "\n".join(
                f"- {s.get('name', '?')}: {s.get('description', '')[:100]}" for s in existing_skills
            )
            or "(none)"
        )
        return self.REFLECTION_PROMPT_TEMPLATE.format(
            task_description=outcome.description,
            success="yes" if outcome.success else "no",
            duration=outcome.duration_seconds,
            tools=", ".join(outcome.tools_used) or "none",
            skills=", ".join(outcome.skills_activated) or "none",
            errors="; ".join(outcome.errors_encountered) or "none",
            feedback=outcome.user_feedback or "none",
            excerpt=outcome.conversation_excerpt[:3000] or "(not available)",
            skills_inventory=skills_text,
        )

    def _parse_reflection(self, response: str, outcome: TaskOutcome) -> ReflectionResult:
        """Parse the LLM's JSON response into a ReflectionResult."""
        # Try to extract JSON from markdown code fences or plain text.
        text = response.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Could not parse reflection JSON, using heuristic fallback")
            return self._heuristic_reflect(outcome)

        insights = [
            ReflectionInsight(
                category=i.get("category", "unknown"),
                description=i.get("description", ""),
                evidence=i.get("evidence", ""),
                confidence=float(i.get("confidence", 0.5)),
                affected_skill=i.get("affected_skill"),
            )
            for i in data.get("insights", [])
        ]

        return ReflectionResult(
            insights=insights,
            proposed_skill_changes=data.get("proposed_changes", []),
            self_assessment=data.get("self_assessment", ""),
            confidence=float(data.get("confidence", 0.5)),
        )

    def _heuristic_reflect(self, outcome: TaskOutcome) -> ReflectionResult:
        """Rule-based reflection fallback when no LLM is available."""
        insights: list[ReflectionInsight] = []

        if not outcome.success and outcome.errors_encountered:
            insights.append(
                ReflectionInsight(
                    category="antipattern",
                    description=f"Task failed due to: {'; '.join(outcome.errors_encountered[:3])}",
                    evidence=outcome.conversation_excerpt[:200],
                    confidence=0.8,
                )
            )

        if outcome.tools_used:
            insights.append(
                ReflectionInsight(
                    category="pattern",
                    description=f"Successfully used tools: {', '.join(outcome.tools_used)}",
                    confidence=0.6,
                )
            )

        if outcome.user_feedback:
            sentiment = (
                "positive"
                if any(
                    w in outcome.user_feedback.lower()
                    for w in ["thanks", "great", "good", "perfect", "谢谢", "好"]
                )
                else "needs_attention"
            )
            insights.append(
                ReflectionInsight(
                    category="improvement" if sentiment == "needs_attention" else "pattern",
                    description=f"User feedback: {outcome.user_feedback[:200]}",
                    confidence=0.7,
                )
            )

        return ReflectionResult(
            insights=insights,
            self_assessment=f"Heuristic reflection on task: {outcome.description[:100]}",
            confidence=0.4,
        )

    def _create_proposal_from_change(
        self,
        change: dict[str, Any],
        reflection: ReflectionResult,
        outcome: TaskOutcome,
    ) -> None:
        """Convert a reflection change into a Skill Forge proposal."""
        change_type = change.get("type", "new_skill")
        try:
            proposal_type = ProposalType(change_type)
        except ValueError:
            proposal_type = ProposalType.NEW_SKILL

        self.forge.create_proposal(
            title=change.get(
                "title", f"Skill change from reflection on {outcome.description[:40]}"
            ),
            description=change.get("rationale", "")
            + f"\n\nSelf-assessment: {reflection.self_assessment}",
            proposal_type=proposal_type,
            target_skill=change.get("target_skill"),
            insights=reflection.insights,
            tags=["auto-reflection", change_type],
        )

    @property
    def history(self) -> list[ReflectionResult]:
        """Return all past reflection results."""
        return list(self._history)

    def render_history(self, limit: int = 5) -> str:
        """Render recent reflection history."""
        if not self._history:
            return "No reflections yet."
        lines = [f"## Reflection History (last {min(limit, len(self._history))})", ""]
        for r in self._history[-limit:]:
            lines.append(
                f"### {r.timestamp.strftime('%Y-%m-%d %H:%M')} (confidence: {r.confidence:.2f})"
            )
            if r.self_assessment:
                lines.append(r.self_assessment)
            for i in r.insights[:5]:
                icon = {
                    "pattern": "✓",
                    "antipattern": "✗",
                    "shortcut": "⚡",
                    "gap": "◌",
                    "improvement": "↑",
                }.get(i.category, "•")
                lines.append(f"  {icon} [{i.category}] {i.description[:100]}")
            lines.append("")
        return "\n".join(lines)
