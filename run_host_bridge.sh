#!/usr/bin/env bash
# Linux/macOS launcher for KrokBot Host API Bridge
set -e

echo "============================================================"
echo "  Launching KrokBot Host API Bridge (Unix Host)"
echo "============================================================"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    PYTHON_EXE=".venv/bin/python"
else
    PYTHON_EXE="python3"
fi

exec $PYTHON_EXE run_host_bridge.py
