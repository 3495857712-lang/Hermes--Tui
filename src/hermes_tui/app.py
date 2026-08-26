"""Public application entry for Hermes TUI.

``hermes-tui`` and ``from hermes_tui.app import HermesTUI`` both resolve
here so the CLI does not need to know about ``ui.app`` internals.
"""

from __future__ import annotations

from .bootstrap import HermesRuntime, build_runtime, create_app
from .ui.app import HermesApp

# Historical / CLI name used by __main__ and docs.
HermesTUI = HermesApp

__all__ = [
    "HermesApp",
    "HermesRuntime",
    "HermesTUI",
    "build_runtime",
    "create_app",
]
