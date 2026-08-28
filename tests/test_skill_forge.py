"""Tests for the Skill Forge module."""

from __future__ import annotations

import pytest

from hermes_tui.skill_forge import (
    ProposalStatus,
    ProposalType,
    ReflectionInsight,
    SkillDiff,
    SkillForge,
    SkillProposal,
)


@pytest.fixture()
def forge() -> SkillForge:
    return SkillForge()


@pytest.fixture()
def sample_insight() -> ReflectionInsight:
    return ReflectionInsight(
        category="pattern",
        description="Users often ask for test generation",
        evidence='User said "write tests for this"',
        confidence=0.85,
        affected_skill=None,
    )


class TestProposalCreation:
    def test_create_new_skill_proposal(
        self, forge: SkillForge, sample_insight: ReflectionInsight
    ) -> None:
        p = forge.create_proposal(
            title="Add test generation skill",
            description="Users frequently request test generation",
            proposal_type=ProposalType.NEW_SKILL,
            insights=[sample_insight],
        )
        assert p.id == "SP-0001"
        assert p.status == ProposalStatus.PROPOSED
        assert p.proposal_type == ProposalType.NEW_SKILL
        assert len(p.insights) == 1

    def test_create_modify_proposal(self, forge: SkillForge) -> None:
        p = forge.create_proposal(
            title="Improve code review skill",
            description="Add security checks",
            proposal_type=ProposalType.MODIFY_SKILL,
            target_skill="code-reviewer",
        )
        assert p.target_skill == "code-reviewer"
        assert p.id == "SP-0001"

    def test_proposal_ids_increment(self, forge: SkillForge) -> None:
        p1 = forge.create_proposal("P1", "d", ProposalType.NEW_SKILL)
        p2 = forge.create_proposal("P2", "d", ProposalType.NEW_SKILL)
        p3 = forge.create_proposal("P3", "d", ProposalType.NEW_SKILL)
        assert p1.id == "SP-0001"
        assert p2.id == "SP-0002"
        assert p3.id == "SP-0003"


class TestProposalWorkflow:
    def test_submit_for_review(self, forge: SkillForge) -> None:
        p = forge.create_proposal("T", "d", ProposalType.NEW_SKILL)
        p.status = ProposalStatus.DRAFT
        result = forge.submit_for_review(p.id)
        assert result.status == ProposalStatus.PROPOSED

    def test_accept_proposal(self, forge: SkillForge) -> None:
        p = forge.create_proposal("T", "d", ProposalType.NEW_SKILL)
        result = forge.accept(p.id, "Looks good")
        assert result.status == ProposalStatus.ACCEPTED
        assert len(result.review_comments) == 1

    def test_reject_proposal(self, forge: SkillForge) -> None:
        p = forge.create_proposal("T", "d", ProposalType.NEW_SKILL)
        result = forge.reject(p.id, "Not needed")
        assert result.status == ProposalStatus.REJECTED
        assert "Not needed" in result.review_comments[0]["body"]

    def test_merge_requires_acceptance(self, forge: SkillForge) -> None:
        p = forge.create_proposal("T", "d", ProposalType.NEW_SKILL)
        with pytest.raises(ValueError, match="must be accepted"):
            forge.merge(p.id)

    def test_merge_accepted(self, forge: SkillForge) -> None:
        p = forge.create_proposal("T", "d", ProposalType.NEW_SKILL)
        forge.accept(p.id)
        result = forge.merge(p.id)
        assert result.status == ProposalStatus.MERGED

    def test_start_review(self, forge: SkillForge) -> None:
        p = forge.create_proposal("T", "d", ProposalType.NEW_SKILL)
        result = forge.start_review(p.id)
        assert result.status == ProposalStatus.REVIEWING


class TestQueries:
    def test_list_all_proposals(self, forge: SkillForge) -> None:
        forge.create_proposal("P1", "d", ProposalType.NEW_SKILL)
        forge.create_proposal("P2", "d", ProposalType.MODIFY_SKILL)
        assert len(forge.list_proposals()) == 2

    def test_filter_by_status(self, forge: SkillForge) -> None:
        p1 = forge.create_proposal("P1", "d", ProposalType.NEW_SKILL)
        forge.create_proposal("P2", "d", ProposalType.NEW_SKILL)
        forge.accept(p1.id)
        accepted = forge.list_proposals(status=ProposalStatus.ACCEPTED)
        assert len(accepted) == 1
        assert accepted[0].id == p1.id

    def test_filter_by_type(self, forge: SkillForge) -> None:
        forge.create_proposal("P1", "d", ProposalType.NEW_SKILL)
        forge.create_proposal("P2", "d", ProposalType.MODIFY_SKILL)
        forge.create_proposal("P3", "d", ProposalType.NEW_SKILL)
        new_skills = forge.list_proposals(proposal_type=ProposalType.NEW_SKILL)
        assert len(new_skills) == 2

    def test_filter_by_tag(self, forge: SkillForge) -> None:
        forge.create_proposal("P1", "d", ProposalType.NEW_SKILL, tags=["auto"])
        forge.create_proposal("P2", "d", ProposalType.NEW_SKILL, tags=["manual"])
        auto = forge.list_proposals(tag="auto")
        assert len(auto) == 1

    def test_pending_reviews(self, forge: SkillForge) -> None:
        p1 = forge.create_proposal("P1", "d", ProposalType.NEW_SKILL)
        forge.create_proposal("P2", "d", ProposalType.NEW_SKILL)
        forge.accept(p1.id)  # no longer pending
        pending = forge.pending_reviews()
        assert len(pending) == 1

    def test_get_nonexistent(self, forge: SkillForge) -> None:
        assert forge.get("SP-9999") is None


class TestSkillDiff:
    def test_render_diff(self) -> None:
        diff = SkillDiff(
            file_path="skills/test/skill.md",
            old_lines=["old line 1", "old line 2"],
            new_lines=["new line 1"],
            hunk_header="Update section",
        )
        rendered = diff.render()
        assert "--- a/skills/test/skill.md" in rendered
        assert "+++ b/skills/test/skill.md" in rendered
        assert "-old line 1" in rendered
        assert "+new line 1" in rendered


class TestProposalSummary:
    def test_summary_contains_status(self, forge: SkillForge) -> None:
        p = forge.create_proposal("My Proposal", "desc", ProposalType.NEW_SKILL)
        summary = p.summary()
        assert "My Proposal" in summary
        assert "new_skill" in summary
        assert "proposed" in summary


class TestReflectionDraft:
    def test_reflect_and_propose_creates_draft(self, forge: SkillForge) -> None:
        p = forge.reflect_and_propose(
            task_description="Write a Python function",
            task_outcome="Successfully wrote it",
            existing_skills=[{"name": "python", "description": "Python coding"}],
        )
        assert p.status == ProposalStatus.DRAFT
        assert "Write a Python function" in p.title
        assert "reflection" in p.tags

    def test_reflect_and_propose_prompt_includes_questions(self, forge: SkillForge) -> None:
        p = forge.reflect_and_propose(
            task_description="Test",
            task_outcome="Done",
        )
        assert "Reflection Questions" in p.description
        assert "patterns" in p.description.lower()


class TestRendering:
    def test_render_empty_queue(self, forge: SkillForge) -> None:
        output = forge.render_queue()
        assert "No pending" in output

    def test_render_queue_with_proposals(
        self, forge: SkillForge, sample_insight: ReflectionInsight
    ) -> None:
        forge.create_proposal(
            "Test proposal",
            "Description",
            ProposalType.NEW_SKILL,
            insights=[sample_insight],
        )
        output = forge.render_queue()
        assert "Test proposal" in output
        assert "Top insight" in output
