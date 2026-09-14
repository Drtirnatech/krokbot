#!/usr/bin/env python3
"""
krokbot-bootstrap: Lightweight Remote Node Deployment & Orchestration Agent
----------------------------------------------------------------------------
Profiles local target hardware, phones home to C2, awaits operator approval,
streams the container image directly into the local Docker daemon, stages GGUF
models, and activates the KrokBot agent container.
"""

import os
import sys
import json
import time
import socket
import shutil
import platform
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

def log(tag: str, message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{tag}] {message}", flush=True)

def get_outbound_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def profile_hardware(host_mount: str = "/host_opt_krokbot") -> dict:
    hostname = socket.gethostname()
    arch = platform.machine()
    
    # Memory profiling
    ram_total_gb = 8.0
    ram_free_gb = 4.0
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            mem_dict = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    mem_dict[key] = int(val)
            if "MemTotal" in mem_dict:
                ram_total_gb = round(mem_dict["MemTotal"] / (1024 * 1024), 2)
            if "MemAvailable" in mem_dict:
                ram_free_gb = round(mem_dict["MemAvailable"] / (1024 * 1024), 2)
            elif "MemFree" in mem_dict:
                ram_free_gb = round(mem_dict["MemFree"] / (1024 * 1024), 2)
        except Exception as e:
            log("WARN", f"Could not parse /proc/meminfo: {e}")

    # Disk profiling
    disk_target = host_mount if os.path.exists(host_mount) else "/"
    try:
        usage = shutil.disk_usage(disk_target)
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
    except Exception:
        disk_free_gb = 50.0

    # GPU profiling
    gpu_info = None
    if os.path.exists("/dev/nvhost-ctrl") or os.path.exists("/dev/nvhost-gpu"):
        gpu_info = "NVIDIA Tegra / Orin GPU"
    elif shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                gpu_info = res.stdout.strip().split("\n")[0]
        except Exception:
            pass

    return {
        "hostname": hostname,
        "ip_address": get_outbound_ip(),
        "arch": arch,
        "ram_total_gb": ram_total_gb,
        "ram_free_gb": ram_free_gb,
        "disk_free_gb": disk_free_gb,
        "gpu_info": gpu_info
    }

def verify_docker_socket(socket_path: str = "/var/run/docker.sock") -> bool:
    if not os.path.exists(socket_path):
        log("ERROR", f"Docker socket not found at '{socket_path}'.")
        log("REMEDIATION", "Ensure the container is run with: -v /var/run/docker.sock:/var/run/docker.sock")
        return False

    try:
        res = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                             capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            log("ERROR", f"Docker daemon communication failed: {res.stderr.strip()}")
            log("REMEDIATION", "Verify host Docker daemon is running and socket permissions are granted.")
            return False
        log("OK", f"Docker Engine connected (v{res.stdout.strip()})")
        return True
    except Exception as e:
        log("ERROR", f"Docker CLI invocation error: {e}")
        return False

def http_json(url: str, method: str = "GET", data: dict = None, headers: dict = None) -> dict:
    req_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_data = resp.read().decode("utf-8")
        return json.loads(res_data) if res_data else {}

def main():
    dry_run = "--dry-run" in sys.argv
    c2_url = os.environ.get("C2_URL", "http://127.0.0.1:5200").rstrip("/")
    enrollment_token = os.environ.get("ENROLLMENT_TOKEN", "")
    host_mount = os.environ.get("HOST_OPT_KROKBOT", "/host_opt_krokbot")
    docker_socket = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
    node_id = os.environ.get("NODE_ID", f"node-{platform.node()}-{int(time.time()) % 100000}")

    print("=" * 65)
    print("      KROKBOT LIGHTWEIGHT EDGE NODE BOOTSTRAP AGENT")
    print("=" * 65)
    log("INFO", f"Bootstrap initialized for node ID: {node_id}")

    # 1. Hardware profiling
    specs = profile_hardware(host_mount)
    log("INFO", f"Hardware Profile: {specs['arch']} | {specs['ram_total_gb']}GB RAM ({specs['ram_free_gb']}GB Free) | {specs['disk_free_gb']}GB Free Disk")
    if specs["gpu_info"]:
        log("INFO", f"Accelerator: {specs['gpu_info']}")

    if dry_run:
        log("DRY-RUN", "Dry-run execution requested. Validating socket and exiting...")
        socket_ok = verify_docker_socket(docker_socket)
        log("DRY-RUN", f"Docker socket check status: {'PASSED' if socket_ok else 'SKIPPED/UNAVAILABLE'}")
        print("Dry run completed successfully.")
        return

    # 2. Verify Docker daemon
    if not verify_docker_socket(docker_socket):
        sys.exit(1)

    if not enrollment_token:
        log("ERROR", "ENROLLMENT_TOKEN environment variable is missing.")
        sys.exit(1)

    # 3. Phone home to C2
    register_payload = {
        "id": node_id,
        "token": enrollment_token,
        **specs
    }
    log("C2", f"Phoning home to Command & Control center at {c2_url}...")
    try:
        reg_res = http_json(f"{c2_url}/api/fleet/enroll/register", method="POST", data=register_payload)
        log("C2", f"Registered with C2: {reg_res.get('message', 'Awaiting operator approval')}")
    except Exception as e:
        log("ERROR", f"Failed to register with C2: {e}")
        sys.exit(1)

    # 4. Polling loop for operator approval
    deploy_config = None
    log("WAIT", "Awaiting operator approval in Command & Control UI...")
    while True:
        try:
            heartbeat = http_json(f"{c2_url}/api/fleet/enroll/heartbeat?node_id={node_id}")
            action = heartbeat.get("action")
            if action == "DEPLOY":
                deploy_config = heartbeat
                log("C2", f"Operator approved deployment! Target model: {heartbeat.get('selected_model')}")
                break
            elif action == "FAILED":
                log("ERROR", "Deployment rejected by C2 operator.")
                sys.exit(1)
        except Exception as e:
            log("WARN", f"Heartbeat poll retry: {e}")
        time.sleep(3)

    selected_model = deploy_config.get("selected_model", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")

    # 5. Check / Load Docker image
    log("STAGE", "[1/4] Checking KrokBot container image...")
    res = subprocess.run(["docker", "image", "inspect", "krokbot_agent:latest"],
                         capture_output=True, text=True)
    if res.returncode == 0:
        log("INFO", "Image krokbot_agent:latest already present in local Docker cache.")
    else:
        log("STAGE", f"[1/4] Streaming Docker image from {c2_url}/api/fleet/dist/image...")
        http_json(f"{c2_url}/api/fleet/enroll/heartbeat", method="POST",
                  data={"node_id": node_id, "progress_percent": 20.0, "progress_status": "STREAMING_IMAGE"})

        image_url = f"{c2_url}/api/fleet/dist/image"
        try:
            with urllib.request.urlopen(image_url, timeout=300) as stream_resp:
                load_proc = subprocess.Popen(["docker", "load"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                shutil.copyfileobj(stream_resp, load_proc.stdin)
                load_proc.stdin.close()
                load_proc.wait()
                if load_proc.returncode != 0:
                    log("WARN", f"docker load output: {load_proc.stderr.read().decode('utf-8')}")
                else:
                    log("OK", "Docker image successfully loaded into local engine.")
        except Exception as e:
            log("WARN", f"Could not stream image tarball directly ({e}); proceeding with local image check...")

    # 6. Stage Model Weights
    log("STAGE", f"[2/4] Staging model weights ({selected_model})...")
    http_json(f"{c2_url}/api/fleet/enroll/heartbeat", method="POST",
              data={"node_id": node_id, "progress_percent": 60.0, "progress_status": "STAGING_MODEL"})

    models_dir = Path(host_mount) / "models"
    try:
        models_dir.mkdir(parents=True, exist_ok=True)
        target_model_file = models_dir / selected_model
        if target_model_file.exists() and target_model_file.stat().st_size > 1000000:
            log("OK", f"Model {selected_model} already exists at {target_model_file}.")
        else:
            log("C2", f"Streaming {selected_model} from C2 depot...")
            model_url = f"{c2_url}/api/fleet/dist/models/{selected_model}"
            with urllib.request.urlopen(model_url, timeout=600) as model_resp, open(target_model_file, "wb") as f_out:
                shutil.copyfileobj(model_resp, f_out)
            log("OK", f"Model successfully saved to {target_model_file}")
    except Exception as e:
        log("WARN", f"Direct model staging notice: {e}. Model will use pre-existing or fallback weights.")

    # 7. Start Agent Container
    log("STAGE", "[3/4] Launching KrokBot Agent container...")
    http_json(f"{c2_url}/api/fleet/enroll/heartbeat", method="POST",
              data={"node_id": node_id, "progress_percent": 85.0, "progress_status": "STARTING_CONTAINER"})

    subprocess.run(["docker", "rm", "-f", "krokbot_agent"], capture_output=True)
    run_cmd = [
        "docker", "run", "-d",
        "--name", "krokbot_agent",
        "--restart", "unless-stopped",
        "-p", "5150:5150",
        "-p", "8081:8081",
        "-p", "8992:8992",
        "-v", "/opt/krokbot/models:/app/models",
        "-v", "/opt/krokbot/data:/app/data",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "krokbot_agent:latest"
    ]
    launch_res = subprocess.run(run_cmd, capture_output=True, text=True)
    if launch_res.returncode != 0:
        log("ERROR", f"Failed to run krokbot_agent: {launch_res.stderr.strip()}")
        sys.exit(1)
    log("OK", "krokbot_agent container launched.")

    # 8. Notify completion
    log("STAGE", "[4/4] Finalizing deployment and notifying Command Center...")
    endpoint_url = f"http://{specs['ip_address']}:5150"
    try:
        http_json(f"{c2_url}/api/fleet/enroll/complete", method="POST",
                  data={"node_id": node_id, "endpoint_url": endpoint_url})
        log("SUCCESS", f"Node successfully enrolled and active at {endpoint_url}")
    except Exception as e:
        log("WARN", f"Completion notification notice: {e}")

    print("=" * 65)
    print(f"DEPLOYMENT COMPLETE: KrokBot Agent is now active on {endpoint_url}")
    print("Field engineers can view live logs with: docker logs -f krokbot_agent")
    print("=" * 65)

if __name__ == "__main__":
    main()
