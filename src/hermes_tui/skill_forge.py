"""
Skill Forge — self-evolving skill proposals.

After completing a task, the agent reflects on what went well, what
didn't, and what could be systematised.  The Skill Forge turns these
reflections into *skill proposals* — structured diffs against existing
skills (or entirely new skills) that the user can review, edit, and
merge — like a Pull Request for the agent's own knowledge.

This implements Hermes Agent's core "self-evolution" loop
(Observe → Execute → Reflect → Crystallize → Reuse) in a way that's
auditable and human-in-the-loop, rather than silently mutating prompts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ProposalStatus(str, Enum):
    """Lifecycle of a skill proposal."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    REVIEWING = "reviewing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MERGED = "merged"
    SUPERSEDED = "superseded"


class ProposalType(str, Enum):
    """What kind of skill change is proposed."""

    NEW_SKILL = "new_skill"
    MODIFY_SKILL = "modify_skill"
    DELETE_SKILL = "delete_skill"
    ADD_REFERENCE = "add_reference"
    ADD_SCRIPT = "add_script"
    IMPROVE_DESCRIPTION = "improve_description"


@dataclass
class SkillDiff:
    """A single hunk of change to a skill file.

    Uses a simple line-based diff format (unified-diff-like) rather than
    requiring a full diff library.
    """

    file_path: str
    old_lines: list[str] = field(default_factory=list)
    new_lines: list[str] = field(default_factory=list)
    context_start: int = 0
    hunk_header: str = ""

    def render(self) -> str:
        """Render as a unified-diff-style hunk."""
        lines = [f"--- a/{self.file_path}", f"+++ b/{self.file_path}"]
        if self.hunk_header:
            lines.append(f"@@ {self.hunk_header} @@")
        for line in self.old_lines:
            lines.append(f"-{line}")
        for line in self.new_lines:
            lines.append(f"+{line}")
        return "\n".join(lines)


@dataclass
class ReflectionInsight:
    """A single insight extracted from post-task reflection.

    Attributes:
        category: What kind of insight (pattern, antipattern, shortcut, gap).
        description: What was observed.
        evidence: Concrete example from the task.
        confidence: 0.0–1.0 how confident the agent is.
        affected_skill: Existing skill this relates to, if any.
    """

    category: str
    description: str
    evidence: str = ""
    confidence: float = 0.5
    affected_skill: str | None = None


@dataclass
class SkillProposal:
    """A proposed change to the agent's skill set.

    Analogous to a GitHub Pull Request: it has a title, description,
    diffs, review comments, and a merge/reject decision.

    Attributes:
        id: Unique proposal ID.
        title: Short summary of the change.
        description: Detailed rationale (from reflection).
        proposal_type: New skill, modification, deletion, etc.
        target_skill: Name of the affected skill (None for new skills).
        diffs: File-level changes.
        insights: Reflection insights that motivated this proposal.
        status: Current lifecycle status.
        author: Who created it (agent / user).
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
        review_comments: Human/agent review feedback.
        test_results: Results of any validation runs.
        supersedes: ID of proposal this replaces.
        tags: Categorisation tags.
    """

    id: str
    title: str
    description: str
    proposal_type: ProposalType
    target_skill: str | None = None
    diffs: list[SkillDiff] = field(default_factory=list)
    insights: list[ReflectionInsight] = field(default_factory=list)
    status: ProposalStatus = ProposalStatus.DRAFT
    author: str = "agent"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    review_comments: list[dict[str, Any]] = field(default_factory=list)
    test_results: dict[str, Any] | None = None
    supersedes: str | None = None
    tags: list[str] = field(default_factory=list)

    def add_comment(self, author: str, body: str) -> None:
        """Add a review comment."""
        self.review_comments.append(
            {
                "author": author,
                "body": body,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self.updated_at = datetime.now(UTC)

    def render_diff(self) -> str:
        """Render all diffs in the proposal."""
        return "\n\n".join(d.render() for d in self.diffs)

    def summary(self) -> str:
        """One-line summary."""
        icon = {
            ProposalType.NEW_SKILL: "✨",
            ProposalType.MODIFY_SKILL: "📝",
            ProposalType.DELETE_SKILL: "🗑️",
            ProposalType.ADD_REFERENCE: "📄",
            ProposalType.ADD_SCRIPT: "🔧",
            ProposalType.IMPROVE_DESCRIPTION: "🎯",
        }.get(self.proposal_type, "❓")
        status_icon = {
            ProposalStatus.DRAFT: "📝",
            ProposalStatus.PROPOSED: "🔔",
            ProposalStatus.REVIEWING: "👀",
            ProposalStatus.ACCEPTED: "✅",
            ProposalStatus.REJECTED: "❌",
            ProposalStatus.MERGED: "🎉",
            ProposalStatus.SUPERSEDED: "🔄",
        }.get(self.status, "❓")
        return (
            f"{icon} {status_icon} [{self.id}] {self.title} "
            f"({self.proposal_type.value}, {self.status.value})"
        )


class SkillForge:
    """Manages the reflection → proposal → review → merge cycle.

    The forge does not automatically modify skills; it produces
    proposals that require human (or higher-level agent) approval.
    This keeps self-evolution safe and auditable.
    """

    def __init__(self) -> None:
        self._proposals: dict[str, SkillProposal] = {}
        self._counter: int = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"SP-{self._counter:04d}"

    # ------------------------------------------------------------------
    # Reflection → Proposal
    # ------------------------------------------------------------------
    def create_proposal(
        self,
        title: str,
        description: str,
        proposal_type: ProposalType,
        target_skill: str | None = None,
        insights: list[ReflectionInsight] | None = None,
        diffs: list[SkillDiff] | None = None,
        tags: list[str] | None = None,
    ) -> SkillProposal:
        """Create a new skill proposal.

        Args:
            title: Short summary.
            description: Rationale and expected impact.
            proposal_type: Kind of change.
            target_skill: Existing skill name (if modifying).
            insights: Reflection insights motivating this.
            diffs: Actual file changes.
            tags: Categorisation tags.

        Returns:
            The created proposal.
        """
        pid = self._next_id()
        proposal = SkillProposal(
            id=pid,
            title=title,
            description=description,
            proposal_type=proposal_type,
            target_skill=target_skill,
            diffs=diffs or [],
            insights=insights or [],
            tags=tags or [],
            status=ProposalStatus.PROPOSED,
        )
        self._proposals[pid] = proposal
        logger.info("Skill proposal created: %s — %s", pid, title)
        return proposal

    def reflect_and_propose(
        self,
        task_description: str,
        task_outcome: str,
        existing_skills: list[dict[str, Any]] | None = None,
        conversation_excerpt: str = "",
    ) -> SkillProposal:
        """Generate a proposal from post-task reflection.

        This method builds a structured reflection prompt and would
        typically call the LLM to generate insights and diffs.  In
        practice, the agent loop calls the LLM and passes the parsed
        results to :meth:`create_proposal`; this method provides the
        reflection prompt template and scaffolding.

        Args:
            task_description: What the user asked for.
            task_outcome: What the agent did and how it went.
            existing_skills: List of {name, description, content} for
                skills that were active or relevant.
            conversation_excerpt: Key exchange from the task.

        Returns:
            A draft proposal (to be populated by LLM reflection).
        """
        skills_summary = ""
        if existing_skills:
            skills_summary = "\n".join(
                f"- {s.get('name', '?')}: {s.get('description', '')[:100]}"
                for s in existing_skills
            )

        reflection_prompt = f"""## Task
{task_description}

## Outcome
{task_outcome}

## Relevant Existing Skills
{skills_summary or "(none)"}

## Key Exchange
{conversation_excerpt[:2000]}

## Reflection Questions
1. What patterns or shortcuts made this task succeed?
2. What was missing from the agent's knowledge that caused friction?
3. What should be done differently next time?
4. Is there a reusable procedure, checklist, or template here?
5. Should an existing skill be updated, or is a new skill warranted?

Generate a skill proposal with:
- A clear title
- The type of change (new_skill / modify_skill / etc.)
- Specific file diffs (in Markdown)
- Confidence level (0-1)
"""
        # The agent loop will send this to the LLM, parse the response,
        # and call create_proposal() with the results.
        proposal = self.create_proposal(
            title=f"[Draft] Reflection on: {task_description[:60]}",
            description=reflection_prompt,
            proposal_type=ProposalType.NEW_SKILL,
            tags=["reflection", "auto-reflection", "draft"],
        )
        proposal.status = ProposalStatus.DRAFT
        return proposal

    # ------------------------------------------------------------------
    # Review workflow
    # ------------------------------------------------------------------
    def submit_for_review(self, proposal_id: str) -> SkillProposal:
        """Move a draft to proposed status."""
        p = self._get(proposal_id)
        p.status = ProposalStatus.PROPOSED
        p.updated_at = datetime.now(UTC)
        return p

    def start_review(self, proposal_id: str) -> SkillProposal:
        """Mark a proposal as under review."""
        p = self._get(proposal_id)
        p.status = ProposalStatus.REVIEWING
        p.updated_at = datetime.now(UTC)
        return p

    def accept(self, proposal_id: str, comment: str = "") -> SkillProposal:
        """Accept a proposal (approve for merge)."""
        p = self._get(proposal_id)
        p.status = ProposalStatus.ACCEPTED
        if comment:
            p.add_comment("reviewer", comment)
        return p

    def reject(self, proposal_id: str, reason: str) -> SkillProposal:
        """Reject a proposal with a reason."""
        p = self._get(proposal_id)
        p.status = ProposalStatus.REJECTED
        p.add_comment("reviewer", f"Rejected: {reason}")
        return p

    def merge(self, proposal_id: str) -> SkillProposal:
        """Mark a proposal as merged (applied to skill files)."""
        p = self._get(proposal_id)
        if p.status != ProposalStatus.ACCEPTED:
            raise ValueError(
                f"Proposal {proposal_id} must be accepted before merge "
                f"(current: {p.status.value})"
            )
        p.status = ProposalStatus.MERGED
        p.updated_at = datetime.now(UTC)
        logger.info("Skill proposal merged: %s", proposal_id)
        return p

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get(self, proposal_id: str) -> SkillProposal | None:
        """Return a proposal by ID."""
        return self._proposals.get(proposal_id)

    def _get(self, proposal_id: str) -> SkillProposal:
        p = self._proposals.get(proposal_id)
        if not p:
            raise KeyError(f"Proposal '{proposal_id}' not found")
        return p

    def list_proposals(
        self,
        status: ProposalStatus | None = None,
        proposal_type: ProposalType | None = None,
        tag: str | None = None,
    ) -> list[SkillProposal]:
        """List proposals with optional filters."""
        results = list(self._proposals.values())
        if status:
            results = [p for p in results if p.status == status]
        if proposal_type:
            results = [p for p in results if p.proposal_type == proposal_type]
        if tag:
            results = [p for p in results if tag in p.tags]
        return sorted(results, key=lambda p: p.created_at, reverse=True)

    def pending_reviews(self) -> list[SkillProposal]:
        """Return proposals awaiting review."""
        return self.list_proposals(status=ProposalStatus.PROPOSED)

    def render_queue(self) -> str:
        """Render the proposal queue as a readable list."""
        pending = self.pending_reviews()
        if not pending:
            return "No pending skill proposals."
        lines = ["🔨 Skill Forge — Pending Proposals", "=" * 50]
        for p in pending:
            lines.append(p.summary())
            lines.append(f"   {p.description[:100]}")
            if p.insights:
                top = max(p.insights, key=lambda i: i.confidence)
                lines.append(f"   💡 Top insight: {top.description[:80]}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Serialize all proposals to a dict."""
        return {
            "proposals": [
                {
                    "id": p.id,
                    "title": p.title,
                    "description": p.description,
                    "proposal_type": p.proposal_type.value,
                    "target_skill": p.target_skill,
                    "status": p.status.value,
                    "author": p.author,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat(),
                    "tags": p.tags,
                    "insights": [
                        {
                            "category": i.category,
                            "description": i.description,
                            "evidence": i.evidence,
                            "confidence": i.confidence,
                            "affected_skill": i.affected_skill,
                        }
                        for i in p.insights
                    ],
                    "review_comments": p.review_comments,
                }
                for p in self._proposals.values()
            ]
        }
