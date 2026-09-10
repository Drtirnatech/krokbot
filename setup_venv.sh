#!/usr/bin/env bash
# Bash script to create and set up the KrokBot virtual environment

set -e

echo "============================================================"
echo "  KrokBot Virtual Environment Setup (.venv)"
echo "============================================================"

if [ ! -d ".venv" ]; then
    echo "[1/3] Creating Python virtual environment (.venv)..."
    python3 -m venv .venv
else
    echo "[1/3] Virtual environment (.venv) already exists."
fi

echo "[2/3] Activating virtual environment..."
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

echo "[3/3] Upgrading pip and installing requirements.txt..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo ""
echo "============================================================"
echo "  KrokBot Virtual Environment Setup Complete!"
echo "  To activate, run:      source .venv/bin/activate"
echo "  To start KrokBot, run: python -m krokbot.main"
echo "============================================================"
