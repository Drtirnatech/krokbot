#!/usr/bin/env python3
"""
KrokBot Launcher & Prerequisite Validator
Checks virtual environment, dependencies, and local Ollama LLM before launching.
"""

import sys
import os
import subprocess
import urllib.request
import json

REQUIRED_PACKAGES = ["fastapi", "uvicorn", "psutil", "httpx", "ollama", "pydantic"]
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def print_banner():
    print("=" * 60)
    print("  KrokBot Autonomous Agent Launcher & Health Check")
    print("=" * 60)

def check_and_setup_venv():
    """Ensure .venv exists and active dependencies are installed (for local dev)."""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
            
    if not missing or os.path.exists("/.dockerenv"):
        print("[1/3] Global environment & dependencies active.")
        return

    venv_dir = os.path.join(os.getcwd(), ".venv")
    
    # Determine platform python executable inside .venv
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    if not os.path.exists(venv_dir):
        print("[1/3] Creating virtual environment (.venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
        print("[1/3] Installing requirements.txt into .venv...")
        subprocess.check_call([venv_python, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([venv_python, "-m", "pip", "install", "-r", "requirements.txt"])
    else:
        print("[1/3] Virtual environment (.venv) is present.")

    # Re-exec under .venv python if not currently running inside it
    current_exe = os.path.abspath(sys.executable)
    target_exe = os.path.abspath(venv_python)
    if os.path.exists(target_exe) and current_exe.lower() != target_exe.lower():
        print(f"[1/3] Switching execution to virtual environment ({target_exe})...")
        os.execv(target_exe, [target_exe] + sys.argv)

def check_dependencies():
    """Verify essential packages are loadable."""
    print("[2/3] Validating installed dependencies...")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"      Missing dependencies: {', '.join(missing)}")
        print("      Installing missing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    else:
        print("      All required Python dependencies are verified!")

def check_ollama_llm():
    """Check if local Ollama LLM service is running and responsive."""
    print("[3/3] Checking local Ollama LLM service status...")
    tags_url = f"{OLLAMA_URL}/api/tags"
    
    try:
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                body = json.loads(response.read().decode("utf-8"))
                models = [m.get("name") for m in body.get("models", [])]
                if models:
                    print(f"      Local Ollama LLM active! Available models: {', '.join(models)}")
                else:
                    print("      Local Ollama service is running, but no models were found.")
                    print("      Tip: Pull a model using: 'ollama pull llama3.2'")
                return True
    except Exception as e:
        print("\n" + "!" * 60)
        print(" ERROR: Local Ollama LLM Service is NOT Available!")
        print("!" * 60)
        print(f" Details: Unable to connect to {OLLAMA_URL} ({str(e)})")
        print("\n To resolve this issue:")
        print("   1. Ensure Ollama is installed (https://ollama.com)")
        print("   2. Start the Ollama server in your terminal:")
        print("        ollama serve")
        print("   3. Or pull and run your preferred model:")
        print("        ollama run llama3.2")
        print("!" * 60 + "\n")
        return False
    return True

def main():
    print_banner()
    
    # 1. Setup/Verify Virtual Environment
    check_and_setup_venv()

    # 2. Check Package Dependencies
    check_dependencies()

    # 3. Check Local LLM (Ollama)
    ollama_ready = check_ollama_llm()
    if not ollama_ready:
        print("Exiting launch process due to missing LLM service.")
        sys.exit(1)

    # 4. Launch KrokBot Main
    print("\nStarting KrokBot Agent Orchestrator...\n")
    from krokbot.main import main as krokbot_main
    krokbot_main()

if __name__ == "__main__":
    main()
