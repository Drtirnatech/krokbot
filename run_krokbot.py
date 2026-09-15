#!/usr/bin/env python3
"""
KrokBot Launcher & Prerequisite Validator
Checks virtual environment, dependencies, and local Llama.cpp LLM before launching.
"""

import sys
import os
import subprocess
import urllib.request
import json
import time
from urllib.parse import urlparse

REQUIRED_PACKAGES = ["fastapi", "uvicorn", "psutil", "httpx", "pydantic", "yaml"]
LLAMACPP_URL = os.getenv("LLAMACPP_HOST", "http://127.0.0.1:5155").rstrip("/")

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

def _probe_llamacpp(url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(f"{url}/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                print(f"      Llama.cpp LLM service active at {url}! Loaded models: {models or ['default']}")
                return True
    except Exception:
        pass
    return False

def _find_model_path() -> str:
    env_path = os.getenv("MODEL_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    
    candidates = [
        "/app/models",
        os.path.join(os.getcwd(), "models"),
        os.path.join(os.path.dirname(__file__), "models")
    ]
    for c_dir in candidates:
        if os.path.isdir(c_dir):
            for fname in os.listdir(c_dir):
                if fname.endswith(".gguf"):
                    return os.path.join(c_dir, fname)
    return ""

def ensure_llamacpp_service() -> bool:
    """Ensure Llama.cpp service is available; auto-start if local and model exists."""
    print("[3/3] Checking Llama.cpp LLM service status...")
    from krokbot.model_manager import load_config, ensure_model_available
    
    config = load_config()
    model_cfg = config.get("model", {})
    model_name = model_cfg.get("name", "qwen3-4b")
    os.environ["LLM_MODEL"] = model_name
    
    # Check if already running
    if _probe_llamacpp(LLAMACPP_URL):
        return True

    parsed = urlparse(LLAMACPP_URL)
    hostname = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5155

    is_local = hostname in ("localhost", "127.0.0.1", "0.0.0.0")

    if is_local:
        model_file = ensure_model_available(config)
        if model_file and os.path.exists(model_file):
            n_ctx = str(model_cfg.get("context_size", 2048))
            chat_format = str(model_cfg.get("chat_format", "chatml"))
            print(f"      Starting embedded Llama.cpp server with model: {model_file} (ctx={n_ctx}, format={chat_format}) ...")
            cmd = [
                sys.executable, "-m", "llama_cpp.server",
                "--model", model_file,
                "--host", "0.0.0.0",
                "--port", str(port),
                "--n_ctx", n_ctx,
                "--chat_format", chat_format
            ]
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Wait for startup
                for _ in range(45):
                    time.sleep(1)
                    if _probe_llamacpp(LLAMACPP_URL, timeout=1.5):
                        return True
            except Exception as e:
                print(f"      Failed to spawn llama_cpp.server: {e}")

    # If external (e.g. docker network service) or took a moment to start, wait up to 60s
    print(f"      Waiting for Llama.cpp at {LLAMACPP_URL} ...")
    for _ in range(60):
        time.sleep(1)
        if _probe_llamacpp(LLAMACPP_URL, timeout=2.0):
            return True

    print("\n" + "!" * 60)
    print(" ERROR: Llama.cpp LLM Service is NOT Available!")
    print("!" * 60)
    print(f" Target URL: {LLAMACPP_URL}")
    print("\n To resolve this issue:")
    print("   1. Ensure a GGUF model exists in ./models/ (e.g., Qwen3-4B-Q4_K_M.gguf)")
    print("   2. Start llama-cpp server manually or verify your docker-compose service:")
    print(f"        python -m llama_cpp.server --model <model.gguf> --port {port}")
    print("   3. Or configure LLAMACPP_HOST to point to your running llama.cpp instance.")
    print("!" * 60 + "\n")
    return False

def main():
    print_banner()
    
    # 1. Setup/Verify Virtual Environment
    check_and_setup_venv()

    # 2. Check Package Dependencies
    check_dependencies()

    # 3. Check Llama.cpp LLM
    llm_ready = ensure_llamacpp_service()
    if not llm_ready:
        print("[Notice] LLM engine is offline/unloaded. Starting KrokBot Agent in standby mode on port 5150...")

    # 4. Launch KrokBot Main
    print("\nStarting KrokBot Agent Orchestrator...\n")
    from krokbot.main import main as krokbot_main
    krokbot_main()

if __name__ == "__main__":
    main()
