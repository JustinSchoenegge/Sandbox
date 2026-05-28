#!/bin/bash
set -e

echo "Setting up Dark Hour Dashboard..."

# Create virtual environment if not present
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Created venv"
fi

# Install dependencies
venv/bin/pip install -q -r requirements.txt
echo "  Dependencies installed"

# Create .env from example if not present
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  Created .env — add your ANTHROPIC_API_KEY before running"
fi

# Create data directory
mkdir -p data assets
echo "  Directories ready"

echo ""
echo "Done. To run:"
echo "  source venv/bin/activate"
echo "  python3 tui.py"
echo ""
echo "Or just double-click DarkHour.command on your Desktop (if set up)."
