#!/usr/bin/env bash
# Development environment setup script
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check Python version
info "Checking Python version..."
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "Python 3.11+ required, found $PY_VERSION"
    exit 1
fi
ok "Python $PY_VERSION"

# Create virtual environment
if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv .venv
    ok "Virtual environment created."
else
    info "Virtual environment already exists."
fi

# Activate
# shellcheck disable=SC1091
source .venv/bin/activate

# Upgrade pip
info "Upgrading pip..."
pip install --upgrade pip

# Install package with dev dependencies
info "Installing hermes-tui with dev dependencies..."
pip install -e ".[dev]"

ok "Development environment ready!"
echo ""
echo "Activate with: source .venv/bin/activate"
echo "Run tests:     make test"
echo "Run app:       make run"
echo "Lint:          make lint"
echo "Format:        make format"
