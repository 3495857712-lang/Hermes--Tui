"""Skill discovery and loading system.

Skills are directories containing ``SKILL.md`` files with optional YAML
frontmatter.  They provide the agent with domain-specific instructions
and are loaded in three tiers based on how much context is needed:

* **Tier 1** - name + one-line description (~20 tokens).
* **Tier 2** - name + description + tags + parameter hints (~200 tokens).
* **Tier 3** - the full Markdown body (as many tokens as needed).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils.helpers import parse_yaml_frontmatter, sanitize_filename

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A loaded skill."""

    name: str
    description: str
    body: str
    path: Path
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    use_count: int = 0
    last_used: datetime | None = None

    @property
    def tier1_metadata(self) -> dict[str, str]:
        """Return tier-1 metadata (name + description only)."""
        return {"name": self.name, "description": self.description}

    @property
    def content(self) -> str:
        """Alias for *body* for backward compatibility."""
        return self.body


class SkillLoader:
    """Discovers, loads, and ranks skills from a directory.

    A *skills directory* contains subdirectories, each holding a
    ``SKILL.md`` file::

        skills/
            weather/
                SKILL.md
            code-review/
                SKILL.md
    """

    SKILL_FILENAME = "SKILL.md"

    def __init__(self, skills_dir: Path, db: Any = None) -> None:
        self.skills_dir = Path(skills_dir).expanduser()
        self.db = db
        self._skills: dict[str, Skill] = {}

    # ------------------------------------------------------------------
    # Discovery & loading
    # ------------------------------------------------------------------

    def discover(self) -> list[Skill]:
        """Scan immediate subdirectories for ``SKILL.md`` files.

        Returns an empty list when the skills directory does not exist.
        """
        self._skills.clear()
        if not self.skills_dir.is_dir():
            return []
        for child in sorted(self.skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_file = child / self.SKILL_FILENAME
            if not skill_file.is_file():
                continue
            try:
                skill = self.load_from_file(skill_file)
                self._skills[skill.name] = skill
            except (OSError, ValueError) as exc:
                logger.warning("Failed to load skill %s: %s", skill_file, exc)
        logger.info("Discovered %d skills", len(self._skills))
        return list(self._skills.values())

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        """Split a Markdown document into YAML frontmatter and body."""
        return parse_yaml_frontmatter(content)

    def load_from_file(self, path: Path) -> Skill:
        """Load a single ``SKILL.md`` file and return a :class:`Skill`."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        meta, body = self.parse_frontmatter(content)

        name = meta.get("name") or path.parent.stem
        name = sanitize_filename(str(name))
        if not name:
            raise ValueError(f"Skill at {path} has no valid name")

        skill = Skill(
            name=name,
            description=str(meta.get("description", "")).strip(),
            version=str(meta.get("version", "1.0.0")),
            tags=[str(t) for t in meta.get("tags", [])],
            body=body.strip(),
            path=path,
            enabled=bool(meta.get("enabled", True)),
        )
        return skill

    # Backwards-compatible alias.
    def load_skill(self, path: Path) -> Skill:
        """Alias for :meth:`load_from_file`."""
        return self.load_from_file(path)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, name: str) -> Skill | None:
        """Return the skill with *name*, or ``None``."""
        return self._skills.get(name)

    def get_skill(self, name: str) -> Skill | None:
        """Alias for :meth:`get`."""
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        """Return all loaded skills."""
        return list(self._skills.values())

    def enabled_skills(self) -> list[Skill]:
        """Return only enabled skills."""
        return [s for s in self._skills.values() if s.enabled]

    def match(self, query: str, top_k: int = 3) -> list[Skill]:
        """Rank enabled skills by keyword overlap with *query*."""
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))
        scored: list[tuple[Skill, float]] = []

        for skill in self._skills.values():
            if not skill.enabled:
                continue
            text = " ".join(
                [skill.name, skill.description, skill.body, " ".join(skill.tags)]
            ).lower()
            text_tokens = set(re.findall(r"\w+", text))
            overlap = query_tokens & text_tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1)
            tag_overlap = query_tokens & {t.lower() for t in skill.tags}
            score += len(tag_overlap) * 0.3
            scored.append((skill, round(score, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:top_k]]

    def match_skills(self, query: str, top_k: int = 3) -> list[tuple[Skill, float]]:
        """Like :meth:`match` but returns ``(skill, score)`` tuples."""
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))
        scored: list[tuple[Skill, float]] = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            text = " ".join(
                [skill.name, skill.description, skill.body, " ".join(skill.tags)]
            ).lower()
            text_tokens = set(re.findall(r"\w+", text))
            overlap = query_tokens & text_tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1)
            tag_overlap = query_tokens & {t.lower() for t in skill.tags}
            score += len(tag_overlap) * 0.3
            scored.append((skill, round(score, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def increment_use_count(self, name: str) -> None:
        """Increment the usage counter for the named skill."""
        skill = self._skills.get(name)
        if skill is None:
            return
        skill.use_count += 1
        skill.last_used = datetime.utcnow()

    def increment_use(self, name: str) -> None:
        """Alias for :meth:`increment_use_count`."""
        self.increment_use_count(name)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a skill. Returns ``False`` if not found."""
        skill = self._skills.get(name)
        if skill is None:
            return False
        skill.enabled = enabled
        return True

    # ------------------------------------------------------------------
    # Skill creation
    # ------------------------------------------------------------------

    def create_example_skill(
        self,
        name: str = "example-skill",
        description: str = "An example skill",
        tags: list[str] | None = None,
    ) -> Skill:
        """Create a ``SKILL.md`` on disk, register it, and return the Skill."""
        tags = tags or ["example"]
        safe_name = sanitize_filename(name)
        skill_dir = self.skills_dir / safe_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / self.SKILL_FILENAME

        tags_str = ", ".join(tags)
        content = (
            "---\n"
            f"name: {safe_name}\n"
            f"description: {description}\n"
            "version: 1.0.0\n"
            f"tags: [{tags_str}]\n"
            "---\n\n"
            f"# {safe_name}\n\n"
            f"{description}\n"
        )
        skill_file.write_text(content, encoding="utf-8")

        skill = self.load_from_file(skill_file)
        self._skills[safe_name] = skill
        logger.info("Created skill %s at %s", safe_name, skill_file)
        return skill

    # ------------------------------------------------------------------
    # Metadata helpers (tiered)
    # ------------------------------------------------------------------

    def get_metadata(self, skill: Skill) -> dict[str, str]:
        """Return tier-1 metadata."""
        return skill.tier1_metadata

    def get_description(self, skill: Skill) -> dict[str, Any]:
        """Return tier-2 metadata."""
        return {
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "tags": skill.tags,
            "parameters": self._extract_parameters(skill.body),
        }

    def get_full_content(self, skill: Skill) -> str:
        """Return the full tier-3 Markdown body."""
        return skill.body

    @staticmethod
    def _extract_parameters(content: str) -> list[dict[str, Any]]:
        params: list[dict[str, Any]] = []
        match = re.search(
            r"##+\s*Parameters\s*\n(.+?)(?=\n##|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return params
        for line in match.group(1).splitlines():
            line = line.strip()
            if not line.startswith("-"):
                continue
            m = re.match(r"-\s*(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.*)", line)
            if m:
                pname, ptype_desc, pdesc = m.groups()
                ptype = "string"
                required = False
                if ptype_desc:
                    parts = [p.strip().lower() for p in ptype_desc.split(",")]
                    ptype = parts[0] if parts else "string"
                    required = "required" in parts
                params.append(
                    {
                        "name": pname,
                        "type": ptype,
                        "description": pdesc,
                        "required": required,
                    }
                )
        return params
