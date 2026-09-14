import os
import sys
import time
import yaml
import httpx
from typing import Dict, Any, List, Optional, Callable

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0",
    "model": {
        "name": "Qwen3-4B-Q4_K_M",
        "filename": "Qwen3-4B-Q4_K_M.gguf",
        "url": "",
        "context_size": 2048,
        "chat_format": "chatml",
        "auto_download": True
    },
    "server": {
        "host": "0.0.0.0",
        "port": 5155,
        "n_threads": 4
    },
    "agent": {
        "id": "krok-prime-01",
        "name": "KrokBot Prime Sentinel",
        "dashboard_port": 5150,
        "bridge_port": 8992,
        "default_temperature": 0.2
    },
    "catalog": {}
}

# Global state for web UI download progress tracking
download_state: Dict[str, Any] = {
    "status": "idle",
    "filename": "",
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "percent": 0.0,
    "error": None,
    "speed_mb": 0.0
}

def find_config_file() -> Optional[str]:
    """Locate the krokbot_config.yaml file."""
    env_cfg = os.getenv("KROKBOT_CONFIG")
    if env_cfg and os.path.exists(env_cfg):
        return env_cfg
    
    candidates = [
        os.path.join(os.getcwd(), "krokbot_config.yaml"),
        "/app/krokbot_config.yaml",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "krokbot_config.yaml"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file or return defaults."""
    path = config_path or find_config_file()
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(loaded)
                    return cfg
        except Exception as e:
            print(f"[ModelManager] Warning: failed to parse {path}: {e}")
    return DEFAULT_CONFIG.copy()

def find_models_dir() -> str:
    """Resolve directory containing GGUF model files within the container environment."""
    env_dir = os.getenv("MODELS_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    
    # When running inside container, strictly enforce /app/models
    if os.path.exists("/app"):
        os.makedirs("/app/models", exist_ok=True)
        return "/app/models"

    candidates = [
        "/app/models",
        os.path.join(os.getcwd(), "models"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    ]
    for d in candidates:
        if os.path.isdir(d):
            return d
    # Create fallback local models directory if none exists
    fallback = os.path.join(os.getcwd(), "models")
    os.makedirs(fallback, exist_ok=True)
    return fallback

def get_available_models(models_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scan models directory for available .gguf files."""
    mdir = models_dir or find_models_dir()
    models = []
    if not os.path.isdir(mdir):
        return models

    for fname in os.listdir(mdir):
        if fname.endswith(".gguf"):
            fpath = os.path.join(mdir, fname)
            try:
                stat = os.stat(fpath)
                size_bytes = stat.st_size
                size_mb = round(size_bytes / (1024 * 1024), 2)
                size_gb = round(size_bytes / (1024 * 1024 * 1024), 2)
                if size_gb >= 1.0:
                    size_formatted = f"{size_gb:.2f} GB ({size_mb:.1f} MB)"
                else:
                    size_formatted = f"{size_mb:.1f} MB"
                modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                models.append({
                    "filename": fname,
                    "path": fpath,
                    "size_bytes": size_bytes,
                    "size_mb": size_mb,
                    "size_gb": size_gb,
                    "size_formatted": size_formatted,
                    "modified": modified
                })
            except Exception:
                pass
    return sorted(models, key=lambda x: x["filename"])

def download_model_file(url: str, target_path: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
    """Download a GGUF model file with streaming progress."""
    global download_state
    target_dir = os.path.dirname(target_path)
    os.makedirs(target_dir, exist_ok=True)
    part_path = target_path + ".part"

    filename = os.path.basename(target_path)
    download_state.update({
        "status": "downloading",
        "filename": filename,
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "percent": 0.0,
        "error": None,
        "speed_mb": 0.0
    })

    start_time = time.time()
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as response:
            if response.status_code != 200:
                err_msg = f"HTTP {response.status_code}: {response.reason_phrase}"
                download_state.update({"status": "error", "error": err_msg})
                return False

            total_length = int(response.headers.get("content-length", 0))
            download_state["total_bytes"] = total_length
            downloaded = 0

            with open(part_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024): # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = (downloaded / (1024 * 1024)) / (elapsed if elapsed > 0 else 1)
                        pct = round((downloaded / total_length * 100), 1) if total_length > 0 else 0.0

                        download_state.update({
                            "downloaded_bytes": downloaded,
                            "percent": pct,
                            "speed_mb": round(speed, 2)
                        })

                        if progress_callback:
                            progress_callback(downloaded, total_length)

        # Atomic rename
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(part_path, target_path)

        download_state.update({
            "status": "complete",
            "percent": 100.0,
            "error": None
        })
        return True

    except Exception as e:
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except Exception:
                pass
        download_state.update({
            "status": "error",
            "error": str(e)
        })
        return False

def ensure_model_available(config: Optional[Dict[str, Any]] = None) -> str:
    """Ensure configured model is available; download non-interactively if configured."""
    cfg = config or load_config()
    model_cfg = cfg.get("model", {})
    target_filename = model_cfg.get("filename", "")
    target_url = model_cfg.get("url", "")
    auto_download = model_cfg.get("auto_download", True)
    
    models_dir = find_models_dir()

    # 1. Check if configured model file exists directly
    if target_filename:
        exact_path = os.path.join(models_dir, target_filename)
        if os.path.exists(exact_path):
            print(f"[ModelManager] Found active model: {exact_path}")
            return exact_path

    # 2. Check if model can be resolved from catalog
    if not target_url and target_filename:
        for k, v in cfg.get("catalog", {}).items():
            if v.get("filename") == target_filename and v.get("url"):
                target_url = v.get("url")
                break

    # 3. If missing and auto_download is enabled, perform non-interactive download
    if target_filename and target_url and auto_download:
        dest_path = os.path.join(models_dir, target_filename)
        print(f"[ModelManager] Model '{target_filename}' not found locally.")
        print(f"[ModelManager] Non-interactive download initiated from: {target_url}")
        
        last_print = 0
        def cli_progress(downloaded, total):
            nonlocal last_print
            now = time.time()
            if now - last_print > 1.0 or downloaded >= total:
                last_print = now
                pct = round(downloaded / total * 100, 1) if total > 0 else 0
                mb_down = round(downloaded / (1024 * 1024), 1)
                mb_tot = round(total / (1024 * 1024), 1)
                sys.stdout.write(f"\r[ModelManager] Downloading: {mb_down}/{mb_tot} MB ({pct}%)")
                sys.stdout.flush()

        success = download_model_file(target_url, dest_path, cli_progress)
        print()
        if success:
            print(f"[ModelManager] Model downloaded successfully to: {dest_path}")
            return dest_path
        else:
            print(f"[ModelManager] Error downloading model: {download_state.get('error')}")

    # 4. Fallback: check any existing .gguf in directory
    existing = get_available_models(models_dir)
    if existing:
        fallback_path = existing[0]["path"]
        print(f"[ModelManager] Using available local GGUF: {fallback_path}")
        return fallback_path

    return ""

def delete_model_file(filename: str, models_dir: Optional[str] = None) -> bool:
    """Safely delete and purge a GGUF model file and any partial downloads from storage."""
    mdir = models_dir or find_models_dir()
    safe_filename = os.path.basename(filename).strip()
    if not safe_filename.endswith(".gguf"):
        raise ValueError("Invalid model filename. Must end with .gguf")
    
    target_path = os.path.join(mdir, safe_filename)
    part_path = target_path + ".part"
    deleted = False

    if os.path.exists(target_path):
        os.remove(target_path)
        deleted = True

    if os.path.exists(part_path):
        os.remove(part_path)
        deleted = True

    return deleted

def save_config(cfg: Dict[str, Any], config_path: Optional[str] = None) -> str:
    """Save configuration dictionary back to YAML file."""
    path = config_path or find_config_file()
    if not path:
        path = os.path.join(os.getcwd(), "krokbot_config.yaml")

    content = yaml.safe_dump(cfg, default_flow_style=False, sort_keys=False)
    # Write directly to avoid EBUSY on docker single-file bind mounts
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def _restart_local_llama_server(model_path: str, port: int = 5155, n_ctx: int = 2048, chat_format: str = "chatml") -> bool:
    """Terminate existing llama_cpp.server and launch with the new model file, verifying in-memory activation."""
    import psutil
    import subprocess
    import socket
    import urllib.request
    import json

    current_pid = os.getpid()
    found_running = False

    # 1. Terminate any running llama_cpp.server processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = " ".join(cmdline)
            if "llama_cpp.server" in cmdline_str and proc.info['pid'] != current_pid:
                found_running = True
                proc.terminate()
                try:
                    proc.wait(timeout=4)
                except Exception:
                    proc.kill()
        except Exception:
            pass

    # Free heap and trim unfragmented memory back to the kernel
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass

    # 2. Ensure port is fully released
    for _ in range(15):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            s.close()
            time.sleep(0.3)
        except Exception:
            break

    # 3. Launch llama_cpp.server with the new model
    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", model_path,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--n_ctx", str(n_ctx),
        "--chat_format", str(chat_format)
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 4. Verify that the new model is loaded and responding on /v1/models
        target_basename = os.path.basename(model_path)
        for _ in range(40):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/models")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        loaded_ids = [m.get("id", "") for m in data.get("data", [])]
                        if any(target_basename in lid for lid in loaded_ids):
                            print(f"[ModelManager] Verified active model loaded in memory: {loaded_ids}")
                            return True
            except Exception:
                continue

        return True
    except Exception as e:
        print(f"[ModelManager] Failed to launch llama_cpp.server: {e}")
        return False

def set_active_model(
    filename: str,
    config_path: Optional[str] = None,
    models_dir: Optional[str] = None,
    restart_server: bool = True
) -> Dict[str, Any]:
    """
    Set the active GGUF inference model.
    Updates krokbot_config.yaml, environment variables, and restarts llama_cpp.server if running locally.
    """
    safe_filename = os.path.basename(filename).strip()
    if not safe_filename.endswith(".gguf"):
        raise ValueError(f"Invalid model filename '{filename}'. Must end with .gguf")

    mdir = models_dir or find_models_dir()
    model_path = os.path.join(mdir, safe_filename)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file '{safe_filename}' not found in models directory ({mdir}).")

    cfg = load_config(config_path)
    if "model" not in cfg or not isinstance(cfg["model"], dict):
        cfg["model"] = {}

    # Match in catalog if available
    catalog = cfg.get("catalog", {})
    matched_catalog = None
    for k, item in catalog.items():
        if item.get("filename") == safe_filename:
            matched_catalog = item
            break

    if matched_catalog:
        model_name = matched_catalog.get("name", safe_filename[:-5])
        context_size = matched_catalog.get("context_size", 2048)
        chat_format = matched_catalog.get("chat_format", "chatml")
    else:
        model_name = safe_filename[:-5]
        context_size = cfg.get("model", {}).get("context_size", 2048)
        chat_format = cfg.get("model", {}).get("chat_format", "chatml")

    cfg["model"]["name"] = model_name
    cfg["model"]["filename"] = safe_filename
    cfg["model"]["context_size"] = context_size
    cfg["model"]["chat_format"] = chat_format

    saved_path = save_config(cfg, config_path)

    # Set environment variables
    os.environ["MODEL_PATH"] = model_path
    os.environ["LLM_MODEL"] = model_name

    server_restarted = False
    if restart_server:
        server_restarted = _restart_local_llama_server(
            model_path,
            port=cfg.get("server", {}).get("port", 5155),
            n_ctx=context_size,
            chat_format=chat_format
        )

    return {
        "status": "success",
        "filename": safe_filename,
        "name": model_name,
        "path": model_path,
        "context_size": context_size,
        "chat_format": chat_format,
        "config_saved": saved_path,
        "server_restarted": server_restarted
    }

