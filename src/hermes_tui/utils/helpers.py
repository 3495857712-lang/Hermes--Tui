"""Utility helper functions for Hermes TUI."""

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path


def generate_id() -> str:
    """Generate a short unique identifier.

    Returns:
        A 12-character hex string derived from UUID4.
    """
    return uuid.uuid4().hex[:12]


def truncate(text: str, max_length: int) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: The input text to truncate.
        max_length: Maximum allowed length including ellipsis.

    Returns:
        Truncated text with ``...`` appended if it exceeded *max_length*.
    """
    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return text[: max_length - 3] + "..."


def sanitize_filename(name: str) -> str:
    """Convert an arbitrary string into a safe filename.

    Replaces whitespace with hyphens, removes characters that are not
    alphanumerics, hyphens, underscores, or dots, and strips leading/trailing
    dots.

    Args:
        name: The original filename string.

    Returns:
        A filesystem-safe filename.
    """
    cleaned = re.sub(r"\s+", "-", name.strip())
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "", cleaned)
    cleaned = cleaned.strip(".")
    return cleaned or "unnamed"


def format_timestamp(dt: datetime | None = None) -> str:
    """Format a datetime for display in the UI.

    Args:
        dt: The datetime to format.  Defaults to the current UTC time.

    Returns:
        A string in ``YYYY-MM-DD HH:MM`` format.
    """
    if dt is None:
        dt = datetime.now(UTC)
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown document.

    Frontmatter must be enclosed between two ``---`` lines at the very
    beginning of the string.

    Args:
        content: The full document text.

    Returns:
        A tuple of ``(metadata_dict, body_text)``.  When no frontmatter is
        present the metadata dict is empty and *body_text* is the original
        content unchanged.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return {}, content

    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    # parts[0] == "" before the first ---, parts[1] is the YAML block,
    # parts[2] is the body.
    if len(parts) < 3:
        return {}, content

    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, content

    if not isinstance(metadata, dict):
        return {}, content

    body = parts[2].lstrip("\n")
    return metadata, body


def approx_token_count(text: str) -> int:
    """Estimate the number of tokens in *text*.

    Uses a rough heuristic of ~4 characters per token.

    Args:
        text: The text to measure.

    Returns:
        Approximate token count.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


# Patterns that may indicate prompt-injection attempts.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)", re.I),
    re.compile(r"forget\s+(?:everything|all|previous|prior)", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"new\s+instructions?:", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"act\s+as\s+(?:a|an)\s+DAN", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"do\s+not\s+follow", re.I),
    re.compile(r"override\s+(?:previous|prior|system)", re.I),
]


def detect_prompt_injection(text: str) -> tuple[bool, list[str]]:
    """Scan *text* for potential prompt-injection attempts.

    The detection is heuristic and may produce false positives.

    Args:
        text: The text to scan.

    Returns:
        A tuple ``(detected, matched_patterns)`` where *detected* is ``True``
        when at least one pattern matched, and *matched_patterns* lists the
        human-readable descriptions of every matched rule.
    """
    matched: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    return bool(matched), matched


def safe_path_join(base: Path, *paths: str) -> Path:
    """Join paths while preventing directory-traversal escapes.

    The resulting path is always resolved and checked to be inside *base*.

    Args:
        base: The base directory that the result must stay within.
        *paths: Path components to append.

    Returns:
        The resolved, safe path.

    Raises:
        ValueError: If the resulting path escapes *base*.
    """
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*paths).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(
            f"Path '{candidate}' escapes base directory '{base_resolved}'"
        ) from exc
    return candidate
