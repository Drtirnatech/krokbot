# Architecture Design Specification: Remote Agent Docker Container Deployment

**Status**: Draft / Pending Final User Review  
**Date**: 2026-09-14  
**Author**: Antigravity & KrokBot Core Team  
**Scope**: KrokBot Command Center (C2), Bootstrap Agent Container, and Field Deployment Tooling

---

## 1. Executive Summary & Problem Statement

Currently, adding a new edge device (e.g. an NVIDIA Jetson Orin, edge server, or workstation) to the KrokBot fleet requires manually building or cloning the codebase, compiling dependencies, and configuring ports directly on the host machine.

This specification defines an automated, secure, and NAT/firewall-resilient mechanism to deploy new KrokBot agent containers to blank Docker instances:
1. **Automated C2 Push with Phone-Home Bootstrap**: A lightweight container (`krokbot-bootstrap`, <30 MB) launched with a single standard `docker run` command on the target host. It queries host hardware, phones home to the Command Center via outbound HTTPS, and waits in an approval queue. Once approved by the C2 operator, the Command Center streams the agent Docker image and selected GGUF model weights directly to the edge node without needing public Docker registries or inbound open ports.
2. **Manual Air-Gapped Deployment Bundle**: For completely isolated or air-gapped environments, a standalone offline bundle with an automated installer (`install.sh` / `install.ps1`) allows field engineers to load the container and models via USB drive in under 3 minutes.
3. **Interactive Engineer Modals & Runbook**: Guided UI modals in the Command Center provide copy-paste commands, real-time download progress, clear diagnostic terminal logs, and a downloadable runbook.

---

## 2. System Architecture & Topology

```
+----------------------------------------------------------------------------------------------------+
|                                    COMMAND & CONTROL CENTER (C2)                                   |
|                                                                                                    |
|   +--------------------------+  +--------------------------+  +--------------------------------+   |
|   |  Token Generator Engine  |  |  Pending Approval Queue  |  |  Direct Stream Depot           |   |
|   |  - Single-use 1hr tokens |  |  - Hardware review &     |  |  - Chunked image streaming     |   |
|   |  - One-click copy snippet|  |    model size selector   |  |  - GGUF model range requests   |   |
|   +--------------------------+  +--------------------------+  +--------------------------------+   |
+--------------------------------------------------^-------------------------------------------------+
                                                   |
                               Outbound HTTPS/WSS  |  (1) Phone-home heartbeat (Token + Specs)
                              (NAT/Firewall Proof) |  (2) Operator Approval Notification
                                                   |  (3) Direct Image & GGUF Model Stream
+--------------------------------------------------v-------------------------------------------------+
|                                 TARGET BLANK HOST (Docker Engine)                                  |
|                                                                                                    |
|   +---------------------------------------+          +-----------------------------------------+   |
|   |        krokbot-bootstrap (<30MB)      |          |              krokbot_agent              |   |
|   |  - Minimal Alpine + Docker CLI socket |          |  - Full Autonomous Multi-Tool Agent     |   |
|   |  - Reads host CPU, RAM, disk, arch    | =======> |  - Embedded Llama.cpp Arbiter (:8081)   |   |
|   |  - Pipes stream directly to docker    |  Spawns  |  - Primary Agent Dashboard (:5150)      |   |
|   |  - Mounts /opt/krokbot host volume    |          |  - Host Hardware Bridge (:8992)         |   |
|   +---------------------------------------+          +-----------------------------------------+   |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Specifications

### 3.1 `krokbot-bootstrap` (Lightweight Facilitation Container)
- **Base Image**: `alpine:3.20` with `curl`, `ca-certificates`, `jq`, and the static Docker CLI binary.
- **Image Size**: < 30 MB compressed.
- **Execution Command**:
  ```bash
  docker run -d --name krokbot-bootstrap --restart unless-stopped \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /opt/krokbot:/host_opt_krokbot \
    -e C2_URL=http://<C2_IP>:5200 \
    -e ENROLL_TOKEN=<TOKEN> \
    ghcr.io/drtirnatech/krokbot-bootstrap:latest
  ```
- **Lifecycle Phases**:
  1. **Pre-flight & Discovery**: Verifies read/write access to `/var/run/docker.sock`. Detects architecture (`aarch64` vs `x86_64`), total and available RAM, and storage free space.
  2. **Phone Home**: Contacts `$C2_URL/api/fleet/enroll/register` with host specs and enrollment token.
  3. **Heartbeat & Standby**: Polls `$C2_URL/api/fleet/enroll/heartbeat` every 3 seconds while waiting for the operator to review and approve the deployment.
  4. **Direct Stream & Docker Load**: Upon receiving `APPROVED`, streams the image payload directly into `docker load` and writes the assigned GGUF model into `/host_opt_krokbot/models/`.
  5. **Orchestration**: Runs `docker run` to spawn `krokbot_agent` with required port mappings (`5150`, `8081`, `8992`) and volume mounts.
  6. **Health Verification & Handshake**: Confirms port 5150 returns `HTTP 200` on `/api/agent/info`, sends `POST /api/fleet/enroll/complete` to C2, and transitions into a passive local watchdog.

---

### 3.2 C2 Command Center Backend Enhancements

#### SQLite Schema Additions (`control_center/src/lib/db.ts`)
```sql
CREATE TABLE IF NOT EXISTS enrollment_tokens (
  token TEXT PRIMARY KEY,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  created_by TEXT DEFAULT 'admin',
  status TEXT NOT NULL DEFAULT 'active' -- 'active', 'claimed', 'expired', 'revoked'
);

CREATE TABLE IF NOT EXISTS pending_nodes (
  id TEXT PRIMARY KEY,
  token TEXT NOT NULL,
  hostname TEXT NOT NULL,
  ip_address TEXT NOT NULL,
  arch TEXT NOT NULL,
  ram_total_gb REAL NOT NULL,
  ram_free_gb REAL NOT NULL,
  disk_free_gb REAL NOT NULL,
  gpu_info TEXT,
  status TEXT NOT NULL DEFAULT 'pending_approval', -- 'pending_approval', 'approved', 'streaming', 'failed', 'completed'
  selected_model TEXT,
  target_node_name TEXT,
  progress_percent REAL DEFAULT 0.0,
  progress_status TEXT,
  last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### API Endpoints (`control_center/src/app/api/fleet/enroll/...`)
1. **`POST /api/fleet/enroll/token`**:
   - Generates a cryptographically secure 32-character token valid for 1 hour.
   - Returns `{ token, expires_at, docker_command }`.
2. **`POST /api/fleet/enroll/register`**:
   - Called by `krokbot-bootstrap` on target startup.
   - Validates token, stores device specs in `pending_nodes`, marks token as `claimed`.
3. **`GET /api/fleet/enroll/pending`**:
   - Returns active pending nodes awaiting operator approval.
4. **`POST /api/fleet/enroll/approve`**:
   - Body: `{ nodeId, selectedModel, nodeName }`.
   - Transitions node state to `approved`.
5. **`GET /api/fleet/enroll/heartbeat`**:
   - Polled by target bootstrap agent. Returns current instruction: `{ action: 'WAIT' | 'DEPLOY' | 'ABORT', model: '...', image_url: '...' }`.
   - Also receives progress updates from the bootstrap container (`progress_percent`, `progress_status`).
6. **`GET /api/fleet/dist/image`**:
   - Validates authorization token.
   - Streams pre-exported gzip archive of `krokbot_agent:latest` directly to the client with `Transfer-Encoding: chunked`.
7. **`GET /api/fleet/dist/models/[filename]`**:
   - Streams requested GGUF model from `./models/` with byte-range support.
8. **`POST /api/fleet/enroll/complete`**:
   - Bootstrap confirms agent is verified healthy. Node is removed from `pending_nodes` and upserted into the active `nodes` table.

---

### 3.3 Manual Air-Gapped Deployment Bundle

For facilities where target machines have no network access to the C2 server:

#### Packaging Script (`scripts/package_offline_node.sh`)
```bash
./scripts/package_offline_node.sh \
  --model qwen2.5-coder-1.5b \
  --output dist/krokbot_offline_bundle.tar.gz
```
Bundle Contents:
```text
krokbot_offline_bundle/
├── images/
│   └── krokbot_agent.tar          # Docker image export (docker save)
├── models/
│   └── qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
├── install.sh                     # Automated Linux / Jetson setup script
├── install.ps1                    # Automated Windows Docker setup script
└── README_ENGINEER.md             # Offline verification runbook
```

#### Target Host Installation Script (`install.sh`)
```bash
#!/usr/bin/env bash
set -e
echo "=== KrokBot Offline Edge Node Installer ==="
# 1. Validate Docker daemon
docker info > /dev/null 2>&1 || { echo "ERROR: Docker daemon is not running!"; exit 1; }

# 2. Load container image
echo "[1/3] Loading Docker image krokbot_agent.tar..."
docker load -i images/krokbot_agent.tar

# 3. Provision persistent volumes
echo "[2/3] Provisioning /opt/krokbot..."
sudo mkdir -p /opt/krokbot/models /opt/krokbot/data
sudo cp models/*.gguf /opt/krokbot/models/

# 4. Launch Container
echo "[3/3] Starting KrokBot Agent..."
docker run -d --name krokbot_agent --restart unless-stopped \
  -p 5150:5150 -p 8081:8081 -p 8992:8992 \
  -v /opt/krokbot/models:/app/models \
  -v /opt/krokbot/data:/app/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  krokbot-agent:latest

echo "SUCCESS: KrokBot Agent active on http://localhost:5150"
```

---

## 4. User Interface & Experience (Command Center)

### 4.1 "+ Enroll / Deploy Node" Modal
- Tabbed design:
  - **Tab 1: Automated C2 Push**: Shows active C2 host IP, 1-click token generator, and copy-to-clipboard command block.
  - **Tab 2: Manual / Air-Gapped Load**: Instructions for creating and deploying offline USB packages, with direct link to download the offline archive.
- Button: **"📄 Download Engineer Runbook (.md)"** downloads `DEPLOYMENT_ENGINEER_RUNBOOK.md` customized with the current C2 server IP.

### 4.2 Pending Nodes Notification & Approval Queue
- Placed directly above the active fleet cards.
- Displays detected hardware cards:
  - **Hostname & IP**: e.g., `jetson-orin-02 (192.168.1.55)`
  - **Hardware Badge**: `ARM64 Jetson Orin • 32 GB RAM • 780 GB Disk`
  - **Dropdown Selector**: Model selection (`Qwen 2.5 Coder 1.5B (1.04 GB)` recommended for edge, `Qwen 3 4B` for high-memory workstations).
  - **Input**: Editable Node Name.
  - **Buttons**: `❌ Reject` and `🚀 Approve & Stream Deploy`.
- **Live Progress Bar**: Displays real-time streaming transfer rate and loading status (`Streaming 42% (38 MB/s)` -> `Extracting` -> `Verified Online`).

---

## 5. Security & Failure Recovery

1. **Authentication**:
   - Enrollment tokens are single-use, cryptographically random, and automatically expire after 60 minutes.
   - Nodes cannot pull image or model streams without an active approved token.
2. **Pre-flight Resource Verification**:
   - Before streaming, C2 checks target free disk space (minimum 5 GB required) and RAM capacity against the chosen model.
3. **Rollback & Conflict Handling**:
   - If port 5150, 8081, or 8992 is already bound on the target host, `krokbot-bootstrap` halts gracefully and prints the conflicting process name and PID.
   - If image streaming is interrupted, the bootstrap agent retries up to 3 times before entering `FAILED` state with explicit remediation advice.

---

## 6. Verification & Test Plan

1. **Unit & API Tests**:
   - Token lifecycle: create, validate, expire, and single-use enforcement (`control_center/tests/enrollment.test.ts`).
   - Pending node queue state machine transitions (`PENDING -> APPROVED -> STREAMING -> ACTIVE`).
   - Direct stream endpoints (`/dist/image` and `/dist/models`) verify chunked streaming and HTTP Range support.
2. **Integration Verification**:
   - Run `krokbot-bootstrap` in a simulated clean container environment.
   - Confirm phone-home registration, hardware spec detection, C2 approval trigger, stream loading, and promotion to active fleet.
3. **Manual Flow Verification**:
   - Run `package_offline_node.sh` to generate an air-gapped bundle and verify `install.sh` executes end-to-end on clean host.

---

## 7. Documentation Deliverables
- `docs/DEPLOYMENT_ENGINEER_RUNBOOK.md`: Comprehensive field engineer manual with pre-flight checks, Linux/Jetson/Windows instructions, offline loading steps, and troubleshooting FAQs.
