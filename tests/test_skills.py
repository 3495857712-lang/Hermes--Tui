"""Tests for hermes_tui.skills module."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hermes_tui.skills import SkillLoader
from hermes_tui.utils.helpers import parse_yaml_frontmatter


class TestFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_parse_frontmatter(self) -> None:
        """Valid frontmatter should be parsed into a dict and body separated."""
        content = textwrap.dedent("""\
            ---
            name: test-skill
            description: A test skill
            tags: [a, b]
            ---

            # Body content
            Some instructions here.
            """)
        meta, body = parse_yaml_frontmatter(content)
        assert meta["name"] == "test-skill"
        assert meta["description"] == "A test skill"
        assert meta["tags"] == ["a", "b"]
        assert "# Body content" in body

    def test_parse_frontmatter_no_frontmatter(self) -> None:
        """Content without frontmatter should return empty dict and full text."""
        content = "# Just a heading\n\nNo frontmatter here."
        meta, body = parse_yaml_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_invalid_frontmatter(self) -> None:
        """Invalid YAML frontmatter should not crash; returns empty dict."""
        content = "---\n: invalid: [yaml\n---\nbody"
        meta, body = parse_yaml_frontmatter(content)
        assert meta == {}
        assert "body" in body


class TestSkillLoading:
    """Tests for loading skills from files."""

    def test_load_skill_from_file(self, sample_skill_dir: Path) -> None:
        """A SKILL.md file should be loaded into a Skill object."""
        loader = SkillLoader(sample_skill_dir.parent)
        skill = loader.load_from_file(sample_skill_dir / "SKILL.md")
        assert skill is not None
        assert skill.name == "example-skill"
        assert skill.description == "An example skill for testing"
        assert "test" in skill.tags
        assert "Example Skill" in skill.body

    def test_discover_skills(self, tmp_path: Path) -> None:
        """discover() should find all SKILL.md files in subdirectories."""
        skills_dir = tmp_path / "skills"
        for name in ("alpha", "beta", "gamma"):
            d = skills_dir / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Skill {name}\n---\nBody of {name}\n",
                encoding="utf-8",
            )

        loader = SkillLoader(skills_dir)
        skills = loader.discover()
        assert len(skills) == 3
        names = {s.name for s in skills}
        assert names == {"alpha", "beta", "gamma"}

    def test_empty_skills_dir(self, tmp_path: Path) -> None:
        """An empty skills directory should return an empty list."""
        skills_dir = tmp_path / "empty_skills"
        skills_dir.mkdir()
        loader = SkillLoader(skills_dir)
        skills = loader.discover()
        assert skills == []

    def test_nonexistent_skills_dir(self, tmp_path: Path) -> None:
        """A non-existent directory should return an empty list."""
        loader = SkillLoader(tmp_path / "does_not_exist")
        assert loader.discover() == []


class TestSkillMetadata:
    """Tests for skill metadata and matching."""

    def test_skill_metadata_tier1(self, sample_skill_dir: Path) -> None:
        """tier1_metadata should only contain name and description."""
        loader = SkillLoader(sample_skill_dir.parent)
        skill = loader.load_from_file(sample_skill_dir / "SKILL.md")
        assert skill is not None
        tier1 = skill.tier1_metadata
        assert set(tier1.keys()) == {"name", "description"}
        assert tier1["name"] == "example-skill"

    def test_skill_match_by_keyword(self, sample_skill_dir: Path) -> None:
        """A keyword present in name/description/tags should match."""
        loader = SkillLoader(sample_skill_dir.parent)
        loader.discover()
        results = loader.match("example")
        assert len(results) >= 1
        assert results[0].name == "example-skill"

    def test_skill_match_by_tag(self, tmp_path: Path) -> None:
        """Skills should be matchable by their tags."""
        skills_dir = tmp_path / "skills"
        d = skills_dir / "weather"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: weather\ndescription: Get weather\ntags: [forecast, rain]\n---\nBody\n",
            encoding="utf-8",
        )
        loader = SkillLoader(skills_dir)
        loader.discover()

        results = loader.match("forecast")
        assert len(results) == 1
        assert results[0].name == "weather"

    def test_skill_match_ranking(self, tmp_path: Path) -> None:
        """Skills that match better should be ranked higher."""
        skills_dir = tmp_path / "skills"
        d1 = skills_dir / "python-expert"
        d1.mkdir(parents=True)
        (d1 / "SKILL.md").write_text(
            "---\nname: python-expert\ndescription: Python coding\ntags: [python]\n---\nBody\n",
            encoding="utf-8",
        )
        d2 = skills_dir / "code-helper"
        d2.mkdir(parents=True)
        (d2 / "SKILL.md").write_text(
            "---\nname: code-helper\ndescription: General python help\ntags: [coding]\n---\nBody\n",
            encoding="utf-8",
        )

        loader = SkillLoader(skills_dir)
        loader.discover()
        results = loader.match("python")
        assert len(results) == 2
        assert results[0].name == "python-expert"

    def test_no_match(self, sample_skill_dir: Path) -> None:
        """A query matching no skills should return an empty list."""
        loader = SkillLoader(sample_skill_dir.parent)
        loader.discover()
        assert loader.match("xyznonexistent") == []


class TestSkillUseAndToggle:
    """Tests for use counting and enable/disable toggles."""

    def test_increment_use_count(self, sample_skill_dir: Path) -> None:
        """increment_use_count should increase the use counter."""
        loader = SkillLoader(sample_skill_dir.parent)
        loader.discover()
        skill = loader.get("example-skill")
        assert skill is not None
        assert skill.use_count == 0
        loader.increment_use_count("example-skill")
        loader.increment_use_count("example-skill")
        assert skill.use_count == 2

    def test_skill_enabled_toggle(self, sample_skill_dir: Path) -> None:
        """Disabling a skill should exclude it from enabled_skills and matching."""
        loader = SkillLoader(sample_skill_dir.parent)
        loader.discover()
        skill = loader.get("example-skill")
        assert skill is not None
        assert skill.enabled is True

        loader.set_enabled("example-skill", False)
        assert skill.enabled is False
        assert loader.enabled_skills() == []
        assert loader.match("example") == []

        loader.set_enabled("example-skill", True)
        assert skill.enabled is True
        assert len(loader.enabled_skills()) == 1

    def test_set_enabled_nonexistent(self, tmp_path: Path) -> None:
        """Toggling a non-existent skill should return False."""
        loader = SkillLoader(tmp_path / "skills")
        assert loader.set_enabled("nope", False) is False


class TestCreateSkill:
    """Tests for programmatically creating skills."""

    def test_create_example_skill(self, tmp_path: Path) -> None:
        """create_example_skill should create a SKILL.md on disk and register it."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        loader = SkillLoader(skills_dir)

        skill = loader.create_example_skill(
            name="my-skill",
            description="My custom skill",
            tags=["custom", "mine"],
        )

        assert skill.name == "my-skill"
        assert (skills_dir / "my-skill" / "SKILL.md").exists()
        assert loader.get("my-skill") is not None

        loader2 = SkillLoader(skills_dir)
        discovered = loader2.discover()
        assert len(discovered) == 1
        assert discovered[0].name == "my-skill"
