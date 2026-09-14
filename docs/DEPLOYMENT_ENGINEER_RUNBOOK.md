# KrokBot Field Deployment Engineer Runbook

> **Target Audience:** Field Systems Engineers, Edge Robotics Technicians, and DevOps Deployment Specialists.  
> **Applicable Hardware:** NVIDIA Jetson (Nano, TX2, Xavier, Orin), Ubuntu/Debian x86_64/ARM64 servers, and Windows 10/11 WSL2 workstations.

---

## 1. Pre-Flight Host Checklist

Before initiating deployment on a blank edge device or server, verify the following prerequisites:

| Check | Requirement | Verification Command | Remediation |
| :--- | :--- | :--- | :--- |
| **Docker Engine** | Docker 20.10+ running | `docker --version` | `sudo apt update && sudo apt install -y docker.io` |
| **Socket Access** | Non-root socket permissions | `docker ps` | `sudo usermod -aG docker $USER && newgrp docker` |
| **RAM** | ≥ 8 GB (16+ GB recommended) | `free -h` | Create an 8GB swapfile if on an 8GB Jetson |
| **Disk Space** | ≥ 15 GB free on root/opt | `df -h /opt` | `docker system prune -a` to free unused space |
| **Outbound Network** | Outbound access to C2 port | `curl -I http://<C2_IP>:5200/api/fleet/nodes` | Configure firewall egress rules for port 5200 |

> [!IMPORTANT]
> **No Inbound Open Ports Required on Target Host:**  
> The KrokBot bootstrap agent communicates via **outbound-only** connections to the Command Center. Edge targets behind NAT, industrial firewalls, or cellular LTE gateways require zero inbound port forwarding to enroll.

---

## 2. Method 1: Automated C2 Push Deployment (Recommended)

Use this method when the blank target host has network connectivity (LAN, VPN, or WAN) to the central Command & Control server.

```
+--------------------------+               +--------------------------+
|  Command Center (C2)     |               |  Blank Edge Host (Docker)|
|                          |               |                          |
|  1. Generate Token       |  Snippet      |                          |
|     (60 min single-use)  | ------------> | 2. Run krokbot-bootstrap |
|                          |               |    container (<30 MB)    |
|                          |  Phone Home   |                          |
|  3. Hardware Pre-flight  | <------------ |    - Profile CPU/RAM/GPU |
|     appears in Queue     |               |    - Test Docker socket  |
|                          |               |                          |
|  4. Operator Approval:   |               |                          |
|     - Select LLM Model   |               |                          |
|     - Assign Node Name   |               |                          |
|                          |  Direct Stream|                          |
|  5. Depot Streams:       | ============> | 5. Streams into:         |
|     - Container Image    |  Chunked Pipe |    - docker load         |
|     - GGUF Weights       |               |    - /opt/krokbot/models |
|                          |               |                          |
|  6. Node Activated       | <------------ | 6. Starts krokbot_agent  |
|     in Fleet Dashboard   |   (Complete)  |    Health check 5150     |
+--------------------------+               +--------------------------+
```

### Step-by-Step Operator & Field Instructions

#### Step 1: Generate Deployment Token in C2
1. Open the Command Center web dashboard (`http://<C2_IP>:5200`).
2. Click the **"+ ENROLL / DEPLOY NODE"** button in the top right header.
3. On the **"1. Automated C2 Push"** tab, click **"Generate Single-Use Enrollment Token (60 min)"**.
4. Click **"📋 Copy Command"** to copy the pre-configured deployment command.

#### Step 2: Execute Command on Blank Host
Open a terminal on the blank target host and run the copied command:

```bash
docker run -d \
  --name krokbot-bootstrap \
  --restart on-failure \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/krokbot:/host_opt_krokbot \
  -e C2_URL="http://<C2_IP>:5200" \
  -e ENROLLMENT_TOKEN="krok-enroll-<TOKEN_HEX>" \
  krokbot-bootstrap:latest
```

#### Step 3: Monitor Bootstrap Progress
Field technicians can stream real-time diagnostic output from the bootstrap container:

```bash
docker logs -f krokbot-bootstrap
```

Expected terminal output:
```text
=================================================================
      KROKBOT LIGHTWEIGHT EDGE NODE BOOTSTRAP AGENT
=================================================================
[2026-09-14 13:57:52] [INFO] Bootstrap initialized for node ID: node-orin-71829
[2026-09-14 13:57:53] [INFO] Hardware Profile: AARCH64 | 31.2GB RAM (27.5GB Free) | 840GB Free Disk
[2026-09-14 13:57:53] [INFO] Accelerator: NVIDIA Tegra / Orin GPU
[2026-09-14 13:57:53] [OK] Docker Engine connected (v24.0.7)
[2026-09-14 13:57:54] [C2] Phoning home to Command & Control center at http://192.168.1.100:5200...
[2026-09-14 13:57:54] [C2] Registered with C2: Node registered for approval
[2026-09-14 13:57:54] [WAIT] Awaiting operator approval in Command & Control UI...
```

#### Step 4: Operator Approval & Model Selection in C2
1. In the Command Center UI, look at the top section: **"/// Pending Nodes — Operator Approval Required"**.
2. Review the detected hardware specifications (Architecture, RAM, Free Disk, GPU).
3. Assign a **Target Node Name** (e.g. `Field Sentinel Orin Alpha`).
4. Select the appropriate **LLM Model**:
   - **Qwen2.5-Coder 1.5B** (1.1 GB): Ideal for Jetson Nano, Orin Nano, and low-RAM devices.
   - **Qwen2.5-Coder 7B** (4.4 GB): Recommended for Orin 32GB/64GB, RTX workstations, and servers.
5. Click **"✓ Approve & Stream Deploy"**.

#### Step 5: Automated Staging & Container Activation
The C2 server automatically streams the container image and model weights directly to the edge node:
- Progress is updated in real time on the C2 progress bar (`STREAMING_IMAGE` -> `STAGING_MODEL` -> `STARTING_CONTAINER`).
- Once loaded, the bootstrap agent spawns `krokbot_agent:latest` and shuts down cleanly.
- The new node immediately transitions into the **Active Fleet Nodes** table.

---

## 3. Method 2: Air-Gapped Offline Installation (USB / Isolated Field Sites)

Use this method for classified, maritime, mining, or completely air-gapped field systems with no LAN/WAN access to the C2 server.

### Step 1: Package Bundle on Connected Workstation

From the KrokBot repository root on a workstation with internet/build access, execute:

```bash
# Linux / macOS:
./scripts/package_offline_node.sh --full

# Windows (PowerShell):
python scripts/package_offline_node.py --full
```

This creates a standalone deployment archive at:
`dist/krokbot-offline-bundle.tar.gz`

Copy this archive onto an encrypted field USB drive or secure transfer medium.

### Step 2: Deploy on Target Linux / NVIDIA Jetson Node

1. Insert the USB drive and copy the archive to `/tmp` or target directory:
   ```bash
   cp /media/usb/krokbot-offline-bundle.tar.gz /home/$USER/
   cd /home/$USER/
   tar -xzf krokbot-offline-bundle.tar.gz
   cd krokbot_offline_bundle
   ```

2. Execute the automated installer:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. The installer performs:
   - Verification of Docker engine and user group permissions.
   - Loading `images/krokbot_agent.tar` into local Docker engine cache.
   - Provisioning persistent host mounts at `/opt/krokbot/models` and `/opt/krokbot/data`.
   - Launching container `krokbot_agent` with restart policies and port bindings (`5150`, `8081`, `8992`).

4. Verify status:
   ```bash
   docker ps
   docker logs -f krokbot_agent
   ```

### Step 3: Deploy on Windows Target (Docker Desktop / WSL2)

1. Open PowerShell as Administrator.
2. Navigate to the extracted bundle:
   ```powershell
   cd C:\path\to\krokbot_offline_bundle
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\install.ps1
   ```

3. The script verifies Docker Desktop, loads the container image, provisions persistent storage at `C:\opt\krokbot`, stages models, and launches the container.

---

## 4. Platform-Specific Optimization Guides

### NVIDIA Jetson (JetPack 5.x / 6.x)

1. **Enable Maximum Performance Power Mode:**
   ```bash
   sudo nvpmodel -m 0
   sudo jetson_clocks
   ```

2. **GPU Docker Acceleration:**
   Verify default runtime is set to NVIDIA in `/etc/docker/daemon.json`:
   ```json
   {
     "default-runtime": "nvidia",
     "runtimes": {
       "nvidia": {
         "path": "nvidia-container-runtime",
         "runtimeArgs": []
       }
     }
   }
   ```
   Restart Docker daemon: `sudo systemctl restart docker`.

3. **Memory Swapping on 8GB Jetson Devices:**
   If running larger models or multi-agent swarms, create an 8GB swap file:
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

### Windows 10/11 WSL2

Configure `.wslconfig` in `C:\Users\<Username>\.wslconfig` to prevent memory exhaustion:
```ini
[wsl2]
memory=16GB
processors=8
swap=8GB
```

---

## 5. Field Diagnostic & Remediation Guide

### Problem: Docker Socket Permission Denied
**Symptom:**
```text
[ERROR] Docker daemon communication failed: permission denied while trying to connect to the Docker daemon socket
```
**Fix:**
```bash
sudo usermod -aG docker $USER
newgrp docker
# Or restart docker service:
sudo systemctl restart docker
```

### Problem: Port Conflict on Port 5150 or 8081
**Symptom:**
```text
docker: Error response from daemon: driver failed programming external connectivity on endpoint krokbot_agent: Bind for 0.0.0.0:5150 failed: port is already allocated.
```
**Fix:**
Identify and stop the conflicting process:
```bash
sudo ss -tulpn | grep -E '5150|8081|8992'
# Terminate old container:
docker rm -f krokbot_agent
```

### Problem: Enrollment Token Expired
**Symptom:**
```text
[ERROR] Failed to register with C2: HTTP Error 401: Invalid or expired enrollment token
```
**Fix:**
Enrollment tokens expire after 60 minutes for security. Generate a fresh token in the Command Center (**"+ ENROLL / DEPLOY NODE"** -> **"Generate Single-Use Enrollment Token"**) and re-run the bootstrap container.

### Problem: Model Inference Memory Allocation Failure
**Symptom:**
```text
llama_model_load: error loading model: not enough memory
```
**Fix:**
1. Switch to a smaller quantized model (e.g. `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`, which uses ~1.2 GB of RAM).
2. Use the C2 SysOps Cleanup button to invoke `malloc_trim` and purge container memory caches.

---

## 6. Verification & Hand-off Checklist

Before handing off the deployed edge node to operations, verify:

- [ ] Web dashboard reachable: `curl -I http://localhost:5150/` returns `200 OK`.
- [ ] VNC stream reachable: `http://<TARGET_IP>:8081` renders noVNC desktop.
- [ ] Host bridge operational: `curl http://localhost:8992/api/system/summary` returns host metrics.
- [ ] Node appears as **ONLINE** in C2 Fleet Dashboard (`http://<C2_IP>:5200`).
- [ ] Test prompt execution passes from C2 command console.
