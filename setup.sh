#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"
TUI="$SCRIPT_DIR/tui.py"
PYTHON="$VENV/bin/python3"

echo ""
echo "  ▸ DARK HOUR — setup"
echo ""

# ── Platform detection ────────────────────────────────────────────────────────
OS_TYPE="$(uname -s 2>/dev/null || echo Unknown)"
echo "  Platform: $OS_TYPE"
if [ "$OS_TYPE" = "Linux" ]; then
    echo "  Note: Security checks are macOS-only. Audio needs mpv or vlc installed."
    echo "        Install with: sudo apt install mpv  OR  sudo dnf install mpv"
    echo ""
fi

# ── Python version check ───────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "  ✗ python3 not found. Install it from https://python.org and re-run."
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PY_VER" -lt 11 ]; then
    echo "  ✗ Python 3.11+ required (found 3.$PY_VER). Update Python and re-run."
    exit 1
fi
echo "  ✓ Python 3.$PY_VER"

# ── Virtual environment ────────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment exists"
fi

# ── Dependencies ───────────────────────────────────────────────────────────────
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "  ✓ Dependencies installed"

# ── Data and asset directories ─────────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/assets"
echo "  ✓ Directories ready"

# ── .env setup ─────────────────────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
fi

# Check if key is still the placeholder
CURRENT_KEY=$(grep "^ANTHROPIC_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
if [ -z "$CURRENT_KEY" ] || [ "$CURRENT_KEY" = "your-key-here" ]; then
    echo ""
    echo "  Anthropic API key — get one free at https://console.anthropic.com"
    echo "  The app works without it (NEON goes silent). Press Enter to skip."
    printf "  API key: "
    read -r API_KEY
    if [ -n "$API_KEY" ] && [ "$API_KEY" != "your-key-here" ]; then
        # Replace or append key in .env
        if grep -q "^ANTHROPIC_API_KEY=" "$ENV_FILE"; then
            sed -i.bak "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$API_KEY|" "$ENV_FILE"
            rm -f "$ENV_FILE.bak"
        else
            echo "ANTHROPIC_API_KEY=$API_KEY" >> "$ENV_FILE"
        fi
        echo "  ✓ API key saved"
    else
        echo "  — Skipped (add it later in .env or via [r] on the Security screen)"
    fi
else
    echo "  ✓ API key already configured"
fi

# ── Shell alias ────────────────────────────────────────────────────────────────
ALIAS_CMD="alias darkhour='$PYTHON $TUI'"

# Detect shell profile
if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
    PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bash_profile" ]; then
    PROFILE="$HOME/.bash_profile"
else
    PROFILE="$HOME/.bashrc"
fi

if grep -q "alias darkhour=" "$PROFILE" 2>/dev/null; then
    # Update existing alias in case path changed
    sed -i.bak "s|alias darkhour=.*|$ALIAS_CMD|" "$PROFILE"
    rm -f "$PROFILE.bak"
    echo "  ✓ darkhour alias updated in $PROFILE"
else
    echo "" >> "$PROFILE"
    echo "# Dark Hour Dashboard" >> "$PROFILE"
    echo "$ALIAS_CMD" >> "$PROFILE"
    echo "  ✓ darkhour alias added to $PROFILE"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "  Done. Open a new terminal tab and run:"
echo ""
echo "      darkhour"
echo ""
echo "  Or launch now with:"
echo ""
echo "      $PYTHON $TUI"
echo ""
