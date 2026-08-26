"""Configuration management for Hermes TUI.

Uses pydantic for validation and supports loading from YAML files and
environment variables with the ``HERMES_TUI_`` prefix.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".hermes-tui"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "memory.db"
DEFAULT_SKILLS_DIR = DEFAULT_CONFIG_DIR / "skills"


class LLMConfig(BaseModel):
    """Configuration for the LLM backend."""

    provider: str = Field(default="openai_compatible")
    base_url: str = Field(default="http://localhost:11434/v1")
    api_key: str = Field(default="ollama")
    model: str = Field(default="qwen2.5:7b")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    timeout: float = Field(default=120.0, ge=1.0)
    max_retries: int = Field(default=3, ge=0)
    stream: bool = Field(default=True)


class AgentConfig(BaseModel):
    """Configuration for the agent orchestration loop."""

    max_tool_iterations: int = Field(default=5, ge=1)
    context_window_tokens: int = Field(default=8000, ge=512)


class UIConfig(BaseModel):
    """Configuration for the TUI appearance and behaviour."""

    theme: str = Field(default="dark", pattern="^(dark|light)$")
    animation: bool = Field(default=True)
    word_wrap: bool = Field(default=True)
    show_token_count: bool = Field(default=True)


class MemoryConfig(BaseModel):
    """Configuration for the memory system."""

    enabled: bool = Field(default=True)
    db_path: str = Field(default=str(DEFAULT_DB_PATH))
    max_entries: int = Field(default=10000, ge=100)
    auto_prune: bool = Field(default=True)
    safety_scan: bool = Field(default=True)


class SkillsConfig(BaseModel):
    """Configuration for the skills system."""

    skills_dir: str = Field(default=str(DEFAULT_SKILLS_DIR))
    auto_load: bool = Field(default=True)
    max_skills: int = Field(default=50, ge=1)


class Config(BaseSettings):
    """Top-level configuration aggregating all sub-configurations."""

    model_config = SettingsConfigDict(
        env_prefix="HERMES_TUI_",
        env_nested_delimiter="__",
        env_file=None,
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> Config:
        """Load configuration from a YAML file and environment variables."""
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        file_data: dict[str, Any] = {}

        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as fh:
                    loaded = yaml.safe_load(fh)
                if isinstance(loaded, dict):
                    file_data = loaded
                    logger.debug("Loaded config from %s", config_path)
            except OSError:
                logger.exception("Failed to read config file: %s", config_path)
                raise
            except yaml.YAMLError:
                logger.exception("Invalid YAML in config file: %s", config_path)
                raise

        return cls(**file_data)

    def save_yaml(self, path: str | Path | None = None) -> Path:
        """Save the current configuration to a YAML file."""
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = self.model_dump()
        with open(config_path, "w", encoding="utf-8") as fh:
            yaml.dump(
                data,
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logger.info("Saved config to %s", config_path)
        return config_path

    @classmethod
    def ensure_default(cls, path: str | Path | None = None) -> tuple[Config, bool]:
        """Ensure a default configuration file exists."""
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH

        if config_path.exists():
            return cls.from_yaml(config_path), False

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = cls()
        config.save_yaml(config_path)
        logger.info("Created default config at %s", config_path)

        config = cls.from_yaml(config_path)
        return config, True


def get_config(
    config_path: str | Path | None = None,
    *,
    create_if_missing: bool = True,
) -> Config:
    """Convenience function to load the application config."""
    if create_if_missing:
        config, _ = Config.ensure_default(config_path)
        return config
    return Config.from_yaml(config_path)


def get_config_dir() -> Path:
    """Return the Hermes TUI configuration directory."""
    env_dir = os.environ.get("HERMES_TUI_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return DEFAULT_CONFIG_DIR
