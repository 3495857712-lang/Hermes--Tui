"""Shared pytest fixtures for Hermes TUI test suite."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hermes_tui.agent import AIAgent
from hermes_tui.config import Config
from hermes_tui.database import DatabaseManager
from hermes_tui.llm import LLMClient, LLMResponse
from hermes_tui.memory import MemoryManager
from hermes_tui.skills import SkillLoader
from hermes_tui.tools import ToolRegistry, register_builtin_tools


@pytest.fixture()
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary configuration directory."""
    config_dir = tmp_path / ".hermes-tui"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database file path."""
    return tmp_path / "test_memory.db"


@pytest.fixture()
def db(tmp_db_path: Path) -> DatabaseManager:
    """Create a DatabaseManager with an initialised schema."""
    manager = DatabaseManager(tmp_db_path)
    yield manager
    manager.close()


@pytest.fixture()
def memory_manager(db: DatabaseManager) -> MemoryManager:
    """Create a MemoryManager backed by a temporary database."""
    return MemoryManager(db, max_entries=100, auto_prune=False)


@pytest.fixture()
def skill_loader(tmp_path: Path) -> SkillLoader:
    """Create a SkillLoader pointing at a temporary skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return SkillLoader(skills_dir)


@pytest.fixture()
def tool_registry(tmp_path: Path) -> ToolRegistry:
    """Create a ToolRegistry with built-in tools registered."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    registry = ToolRegistry(workspace=workspace)
    register_builtin_tools(registry)
    return registry


@pytest.fixture()
def mock_llm_client() -> MagicMock:
    """Create a mock LLMClient with preset chat and stream_chat methods.

    ``chat`` returns a simple LLMResponse with preset content.
    ``stream_chat`` is an async generator yielding preset text chunks.
    """
    client = MagicMock(spec=LLMClient)

    # Default non-streaming response
    default_response = LLMResponse(
        content="Hello! I am Hermes, your AI assistant.",
        model="test-model",
        finish_reason="stop",
    )
    client.chat = AsyncMock(return_value=default_response)

    # Default streaming chunks
    default_chunks = ["Hello", "!", " I", " am", " Hermes", "."]

    async def _mock_stream_chat(*args: Any, **kwargs: Any):
        for chunk in default_chunks:
            yield chunk

    client.stream_chat = _mock_stream_chat
    client.close = AsyncMock()

    # Allow tests to override the return value / chunks
    client._default_response = default_response
    client._default_chunks = default_chunks
    return client


@pytest.fixture()
def sample_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary directory containing an example SKILL.md file."""
    skill_dir = tmp_path / "skills" / "example-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        textwrap.dedent("""\
        ---
        name: example-skill
        description: An example skill for testing
        tags: [test, example]
        enabled: true
        ---

        # Example Skill

        This is an example skill used for testing.
        """),
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    """Write a temporary config file and load a Config from it."""
    config_dir = tmp_path / ".hermes-tui"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"

    # Use Config defaults but override paths to be temp-based
    cfg = Config()
    cfg.memory.db_path = str(tmp_path / "memory.db")
    cfg.skills.skills_dir = str(tmp_path / "skills")
    cfg.save_yaml(config_path)

    loaded = Config.from_yaml(config_path)
    return loaded


@pytest.fixture()
def agent(
    config: Config,
    mock_llm_client: MagicMock,
    memory_manager: MemoryManager,
    skill_loader: SkillLoader,
    tool_registry: ToolRegistry,
) -> AIAgent:
    """Create an AIAgent instance with mock dependencies."""
    return AIAgent(
        config=config,
        llm_client=mock_llm_client,
        memory_manager=memory_manager,
        skill_loader=skill_loader,
        tool_registry=tool_registry,
    )
