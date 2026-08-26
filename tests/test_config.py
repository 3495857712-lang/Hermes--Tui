"""Tests for hermes_tui.config module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from hermes_tui.config import (
    Config,
    LLMConfig,
    get_config,
    get_config_dir,
)


class TestDefaultConfig:
    """Tests for default configuration values."""

    def test_default_config(self) -> None:
        """Default Config values should match expectations."""
        cfg = Config()
        assert cfg.llm.provider == "openai_compatible"
        assert cfg.llm.model == "qwen2.5:7b"
        assert cfg.llm.temperature == 0.7
        assert cfg.llm.max_tokens == 4096
        assert cfg.ui.theme == "dark"
        assert cfg.ui.animation is True
        assert cfg.memory.enabled is True
        assert cfg.memory.max_entries == 10000
        assert cfg.skills.auto_load is True
        assert cfg.skills.max_skills == 50

    def test_llm_config_defaults(self) -> None:
        """LLMConfig defaults should point to a local Ollama instance."""
        llm = LLMConfig()
        assert llm.base_url == "http://localhost:11434/v1"
        assert llm.api_key == "ollama"
        assert llm.model == "qwen2.5:7b"
        assert llm.timeout == 120.0
        assert llm.max_retries == 3


class TestConfigSaveLoad:
    """Tests for saving and loading YAML configuration."""

    def test_config_save_and_load(self, tmp_path: Path) -> None:
        """Saving a config and reloading it should preserve all values."""
        cfg = Config()
        cfg.llm.model = "gpt-4o"
        cfg.llm.temperature = 0.3
        cfg.ui.theme = "light"
        cfg.memory.max_entries = 500

        path = tmp_path / "config.yaml"
        cfg.save_yaml(path)

        loaded = Config.from_yaml(path)
        assert loaded.llm.model == "gpt-4o"
        assert loaded.llm.temperature == 0.3
        assert loaded.ui.theme == "light"
        assert loaded.memory.max_entries == 500

    def test_config_from_yaml(self, tmp_path: Path) -> None:
        """Config should be loadable from an explicit YAML file."""
        path = tmp_path / "my_config.yaml"
        data = {
            "llm": {"model": "llama3", "temperature": 0.9},
            "ui": {"theme": "light"},
        }
        path.write_text(yaml.dump(data), encoding="utf-8")

        cfg = Config.from_yaml(path)
        assert cfg.llm.model == "llama3"
        assert cfg.llm.temperature == 0.9
        assert cfg.ui.theme == "light"
        assert cfg.llm.max_tokens == 4096


class TestEnvOverride:
    """Tests for environment variable overrides."""

    def test_config_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HERMES_TUI_ prefixed env vars should override config values."""
        monkeypatch.setenv("HERMES_TUI_LLM__MODEL", "claude-3-sonnet")
        monkeypatch.setenv("HERMES_TUI_LLM__TEMPERATURE", "0.1")
        monkeypatch.setenv("HERMES_TUI_UI__THEME", "light")

        cfg = Config()
        assert cfg.llm.model == "claude-3-sonnet"
        assert cfg.llm.temperature == 0.1
        assert cfg.ui.theme == "light"


class TestConfigCreation:
    """Tests for auto-creating default config files."""

    def test_config_creates_default(self, tmp_path: Path) -> None:
        """ensure_default should create a config file when none exists."""
        config_path = tmp_path / "newdir" / "config.yaml"
        assert not config_path.exists()

        cfg, created = Config.ensure_default(config_path)
        assert created is True
        assert config_path.exists()
        assert isinstance(cfg, Config)

        cfg2, created2 = Config.ensure_default(config_path)
        assert created2 is False

    def test_config_ensure_dirs(self, tmp_path: Path) -> None:
        """save_yaml should create parent directories."""
        nested = tmp_path / "a" / "b" / "c" / "config.yaml"
        assert not nested.parent.exists()

        cfg = Config()
        cfg.save_yaml(nested)
        assert nested.exists()

    def test_get_config(self, tmp_path: Path) -> None:
        """get_config should create and load a config."""
        path = tmp_path / "config.yaml"
        cfg = get_config(path)
        assert isinstance(cfg, Config)
        assert path.exists()

    def test_get_config_no_create(self, tmp_path: Path) -> None:
        """get_config with create_if_missing=False should work with existing file."""
        path = tmp_path / "config.yaml"
        Config().save_yaml(path)
        cfg = get_config(path, create_if_missing=False)
        assert isinstance(cfg, Config)


class TestInvalidConfig:
    """Tests for error handling with invalid configuration."""

    def test_config_invalid_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML should raise yaml.YAMLError."""
        path = tmp_path / "bad.yaml"
        path.write_text(":\n  invalid: [unclosed", encoding="utf-8")

        with pytest.raises(yaml.YAMLError):
            Config.from_yaml(path)

    def test_get_config_dir_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """get_config_dir should respect HERMES_TUI_CONFIG_DIR env var."""
        custom = str(tmp_path / "custom_config")
        monkeypatch.setenv("HERMES_TUI_CONFIG_DIR", custom)
        assert get_config_dir() == Path(custom)
