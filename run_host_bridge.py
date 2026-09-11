#!/usr/bin/env python3
"""
KrokBot Host API Bridge Launcher
Cross-platform daemon providing the KrokBot agent with authorized access to:
  - Real Host Hardware & Partition Telemetry (disks, CPU, RAM)
  - Host OS Command Line Interface (PowerShell on Windows, Bash on Linux/macOS)
  - Central Tools Policy Governance Enforcement
"""

import sys
import os
import subprocess

def main():
    port = int(os.getenv("BRIDGE_PORT", "8992"))
    host = os.getenv("BRIDGE_HOST", "0.0.0.0")

    print("=" * 60)
    print("  KrokBot Host API Bridge (Native Host Daemon)")
    print("=" * 60)
    print(f"  Operating System: {sys.platform}")
    print(f"  Python Binary:    {sys.executable}")
    print(f"  Listening on:     http://{host}:{port}")
    print("  Security Policy:  agent_tools.json (Tool Policy Manager)")
    print("=" * 60)
    print("\nStarting Uvicorn Host Bridge Server...\n")

    try:
        import uvicorn
        from krokbot.bridge.main import app
        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError:
        print("ERROR: FastAPI or Uvicorn is missing. Installing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        import uvicorn
        from krokbot.bridge.main import app
        uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
