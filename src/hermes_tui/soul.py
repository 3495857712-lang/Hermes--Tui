"""SOUL personality management.

The SOUL file defines the agent's personality, tone, and behavioural
guidelines.  It is stored as plain Markdown so the user can edit it
directly.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SOUL = """# SOUL - Hermes

You are **Hermes**, a self-improving terminal AI agent.

## Personality

- **Rational and precise.** You think clearly and reason step by step.
- **Insightful.** You look beyond the surface question to identify the
  underlying problem.
- **Concise.** You give direct answers without filler, redundancy, or
  excessive hedging.
- **Technically fluent.** You are comfortable with code, systems, and
  complex analysis.
- **Honest.** When you don't know something, you say so rather than
  inventing an answer.

## Behaviour

1. Understand the user's real intent before answering.
2. When a task is ambiguous, state your assumptions and proceed.
3. Use tools when they improve accuracy (search, file access, etc.).
4. Explain trade-offs briefly when presenting options.
5. Never pretend to have executed an action you haven't.
6. Respect the user's time - lead with the answer, add detail only when
   asked or when essential.

## Tone

Speak like a sharp, trusted technical partner.  Friendly but not casual,
confident but not arrogant.  No unnecessary preamble.
"""


class SoulManager:
    """Load, save, and reset the SOUL personality file."""

    def __init__(self, soul_path: Path) -> None:
        """Initialise the manager.

        Args:
            soul_path: Path to the ``SOUL.md`` file.
        """
        self.soul_path = Path(soul_path).expanduser()
        self.soul_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> str:
        """Read the SOUL file, creating a default one if missing.

        Returns:
            The SOUL content as a string.
        """
        if not self.soul_path.exists():
            logger.info("SOUL file not found; creating default at %s", self.soul_path)
            self.save(self.get_default_soul())
        content = self.soul_path.read_text(encoding="utf-8")
        logger.debug("SOUL loaded (%d chars)", len(content))
        return content

    def save(self, content: str) -> Path:
        """Write *content* to the SOUL file.

        Args:
            content: The new SOUL text.

        Returns:
            The path the content was written to.
        """
        self.soul_path.write_text(content, encoding="utf-8")
        logger.info("SOUL saved to %s", self.soul_path)
        return self.soul_path

    def reset(self) -> str:
        """Restore the default SOUL content and persist it.

        Returns:
            The freshly reset SOUL text.
        """
        default = self.get_default_soul()
        self.save(default)
        logger.info("SOUL reset to default")
        return default

    @staticmethod
    def get_default_soul() -> str:
        """Return the built-in default SOUL text."""
        return _DEFAULT_SOUL
