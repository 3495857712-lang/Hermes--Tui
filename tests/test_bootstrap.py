"""Tests for runtime bootstrap and CLI app entry."""

from __future__ import annotations

from pathlib import Path

from hermes_tui.app import HermesTUI, create_app
from hermes_tui.bootstrap import build_runtime
from hermes_tui.config import Config
from hermes_tui.ui.app import HermesApp


def _temp_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.memory.db_path = str(tmp_path / "memory.db")
    cfg.skills.skills_dir = str(tmp_path / "skills")
    return cfg


def test_build_runtime_wires_agent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_TUI_CONFIG_DIR", str(tmp_path / "cfg"))
    runtime = build_runtime(_temp_config(tmp_path))
    assert runtime.agent.current_session is not None
    assert runtime.agent.llm is runtime.llm
    assert len(runtime.tools.list_names()) > 0
    runtime.db.close()


def test_create_app_returns_hermes_app(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_TUI_CONFIG_DIR", str(tmp_path / "cfg"))
    app = create_app(_temp_config(tmp_path))
    assert isinstance(app, HermesApp)
    assert app._agent is not None
    assert app._agent.current_session is not None


def test_hermes_tui_alias() -> None:
    assert HermesTUI is HermesApp
