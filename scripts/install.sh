#!/usr/bin/env bash
# Hermes TUI installation script for Linux and macOS
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Check Python
if ! command -v python3 &>/dev/null; then
    err "Python 3 is required but not found. Install Python 3.11+ and try again."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    err "Python 3.11+ is required. Found Python $PY_VERSION."
    exit 1
fi

ok "Python $PY_VERSION found."

# Prefer pipx if available
if command -v pipx &>/dev/null; then
    info "Installing Hermes TUI with pipx..."
    pipx install hermes-tui
    ok "Installation complete!"
    info "Run 'hermes-tui chat' to start."
    exit 0
fi

# Fall back to pip
info "pipx not found. Installing with pip..."
if [ -n "${VIRTUAL_ENV:-}" ]; then
    pip install hermes-tui
else
    info "Consider using pipx for isolated installation: https://pipx.pypa.io/"
    python3 -m pip install --user hermes-tui
fi

ok "Installation complete!"
info "Run 'hermes-tui chat' to start."
info "If the command is not found, add Python bin directory to your PATH."
