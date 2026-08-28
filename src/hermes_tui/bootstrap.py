"""Runtime bootstrap — wire config into a runnable Hermes stack.

Assembles Database, LLM, Memory, Skills, Tools, PromptBuilder, and
EnhancedAIAgent so the TUI / CLI do not have to know construction order.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config, get_config, get_config_dir
from .database import DatabaseManager
from .enhanced_agent import EnhancedAIAgent
from .llm import LLMClient, create_client
from .memory import MemoryManager
from .prompt import PromptBuilder
from .skills import SkillLoader
from .soul import SoulManager
from .tools import ToolRegistry, register_builtin_tools

logger = logging.getLogger(__name__)


@dataclass
class HermesRuntime:
    """Fully wired application dependencies."""

    config: Config
    db: DatabaseManager
    llm: LLMClient
    memory: MemoryManager
    skills: SkillLoader
    tools: ToolRegistry
    prompt: PromptBuilder
    agent: EnhancedAIAgent


def _resolve_api_key(config: Config) -> str:
    """Prefer env overrides for API keys; fall back to config value."""
    for env_name in (
        "HERMES_TUI_LLM__API_KEY",
        "OPENAI_API_KEY",
        "OLLAMA_API_KEY",
    ):
        value = os.environ.get(env_name)
        if value:
            return value
    return config.llm.api_key


def build_runtime(config: Config | None = None) -> HermesRuntime:
    """Construct all core services and an EnhancedAIAgent."""
    cfg = config or get_config()

    db_path = Path(cfg.memory.db_path).expanduser()
    db = DatabaseManager(db_path)

    llm_cfg = cfg.llm.model_copy(update={"api_key": _resolve_api_key(cfg)})
    llm = create_client(llm_cfg)

    memory = MemoryManager(
        db,
        max_entries=cfg.memory.max_entries,
        auto_prune=cfg.memory.auto_prune,
    )

    skills_dir = Path(cfg.skills.skills_dir).expanduser()
    skills_dir.mkdir(parents=True, exist_ok=True)
    skills = SkillLoader(skills_dir, db=db)
    if cfg.skills.auto_load:
        skills.discover()

    workspace = get_config_dir() / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    tools = ToolRegistry(workspace=workspace)
    register_builtin_tools(tools)

    soul = SoulManager(get_config_dir() / "SOUL.md")
    prompt = PromptBuilder(
        soul_content=soul.load(),
        memory_manager=memory,
        skill_loader=skills,
    )

    agent = EnhancedAIAgent(
        config=cfg,
        llm_client=llm,
        memory=memory,
        skills=skills,
        tools=tools,
        prompt_builder=prompt,
        db=db,
        context_window_tokens=cfg.agent.context_window_tokens,
    )
    agent.create_session()

    logger.info(
        "Runtime ready: model=%s db=%s skills=%d tools=%d",
        cfg.llm.model,
        db_path,
        len(skills.list_skills()),
        len(tools.list_names()),
    )
    return HermesRuntime(
        config=cfg,
        db=db,
        llm=llm,
        memory=memory,
        skills=skills,
        tools=tools,
        prompt=prompt,
        agent=agent,
    )


def create_app(config: Config | None = None) -> Any:
    """Build a fully wired :class:`~hermes_tui.ui.app.HermesApp` instance."""
    from .ui.app import HermesApp

    runtime = build_runtime(config)
    return HermesApp(config=runtime.config, agent=runtime.agent)
