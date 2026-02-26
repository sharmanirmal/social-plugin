#!/usr/bin/env bash
# Social Plugin — macOS/Linux installer
# Usage: curl -sSL https://raw.githubusercontent.com/nirmalsharma/social-plugin/main/scripts/install.sh | bash
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}$*${NC}"; }
ok()    { echo -e "${GREEN}$*${NC}"; }
warn()  { echo -e "${YELLOW}$*${NC}"; }
fail()  { echo -e "${RED}$*${NC}"; exit 1; }

echo -e "${BOLD}Social Plugin — Installer${NC}"
echo ""

# ---- Check Python ----
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    warn "Python 3.11+ not found."
    if command -v brew &>/dev/null; then
        info "Installing Python via Homebrew..."
        brew install python@3.12
        PYTHON="python3.12"
    elif command -v apt-get &>/dev/null; then
        info "Installing Python via apt..."
        sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv python3-pip
        PYTHON="python3.12"
    else
        fail "Please install Python 3.11+ and re-run this script."
    fi
fi

ok "Using $PYTHON ($($PYTHON --version))"

# ---- Check/install pipx ----
if ! command -v pipx &>/dev/null; then
    info "Installing pipx..."
    "$PYTHON" -m pip install --user pipx 2>/dev/null || "$PYTHON" -m pip install pipx
    "$PYTHON" -m pipx ensurepath
    export PATH="$HOME/.local/bin:$PATH"
fi

ok "pipx available"

# ---- Install social-plugin ----
info "Installing social-plugin..."
pipx install social-plugin || pipx upgrade social-plugin

ok "social-plugin installed!"
echo ""

# ---- Run init wizard ----
info "Running setup wizard..."
echo ""
social-plugin init
