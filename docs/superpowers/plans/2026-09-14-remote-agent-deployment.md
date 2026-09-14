# Remote Agent Docker Container Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable automated remote deployment of KrokBot agent Docker containers to blank Docker systems via a lightweight "phone home" bootstrap container, direct C2 image/model streaming, and a self-contained manual air-gapped installation bundle.

**Architecture:** A lightweight Alpine container (`krokbot-bootstrap`, <30 MB) launched on a blank target host queries hardware and phones home to C2 via outbound HTTPS. The C2 Command Center places the node in an operator approval queue, then streams the Docker image tarball and GGUF model directly to the target. For air-gapped environments, a standalone offline bundle with an automated installer enables USB-based deployment in under 3 minutes.

**Architecture Diagram:**

```mermaid
graph TD
    subgraph "Command & Control Center (5200)"
        TG[Token Generator Engine] --> DB[(SQLite Database)]
        PQ[Pending Approval Queue] --> DB
        DIST[Direct Stream Depot] --> SD[Image & Model Stream]
    end

    subgraph "Target Blank Host (Docker)"
        BOOT[krokbot-bootstrap Container]
        DOCK[Local Docker Engine /var/run/docker.sock]
        VOL[/opt/krokbot Volumes]
        MAIN[krokbot_agent Container]
    end

    TG -.->|1. One-line command snippet| BOOT
    BOOT -->|2. Phone home & specs| PQ
    PQ -->|3. Operator Approve & Model Choice| SD
    SD -->|4. Stream chunked image & GGUF| BOOT
    BOOT -->|5. docker load & docker run| DOCK
    DOCK --> MAIN
    MAIN --> VOL
```

**Tech Stack:** Node.js 20, Next.js 16, React 19, SQLite (`node:sqlite`), Docker CLI, Alpine Linux, Bash, PowerShell, Python 3.

## Global Constraints
- Target bootstrap container footprint must remain under 30 MB.
- Outbound HTTPS communication only from edge targets (NAT/firewall-proof).
- Direct C2 streaming: No external connection to Docker Hub or GitHub Container Registry required on edge nodes.
- One-time enrollment tokens expire after 60 minutes.
- All existing tests in `control_center` and `krokbot` must remain 100% green.

---

### Task 1: C2 SQLite Schema & Database Service for Enrollment & Pending Nodes

**Files:**
- Modify: `control_center/src/lib/db.ts`
- Test: `control_center/tests/enrollment-db.test.ts`

**Interfaces:**
- Produces: `createEnrollmentToken`, `validateEnrollmentToken`, `claimEnrollmentToken`, `upsertPendingNode`, `getPendingNodes`, `getPendingNode`, `approvePendingNode`, `updatePendingNodeProgress`, `completePendingNode`, `deletePendingNode`.

- [ ] **Step 1: Write the failing unit tests for enrollment DB operations**

Create `control_center/tests/enrollment-db.test.ts`:
```ts
import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { dbService, setDb, closeDb, initSchema } from '../src/lib/db.ts';

describe('Enrollment & Pending Nodes Database Service', () => {
  let testDb: DatabaseSync;

  beforeEach(() => {
    testDb = new DatabaseSync(':memory:');
    initSchema(testDb);
    setDb(testDb);
  });

  afterEach(() => {
    closeDb();
  });

  it('should create and validate an enrollment token', () => {
    const token = dbService.createEnrollmentToken('admin', 60);
    assert.ok(token, 'Token should be returned');
    assert.equal(typeof token, 'string');
    assert.ok(token.length >= 16);

    const valid = dbService.validateEnrollmentToken(token);
    assert.equal(valid, true);

    const claimed = dbService.claimEnrollmentToken(token);
    assert.equal(claimed, true);

    // Cannot claim twice
    const secondClaim = dbService.claimEnrollmentToken(token);
    assert.equal(secondClaim, false);
  });

  it('should register, approve, and complete a pending node lifecycle', () => {
    const token = dbService.createEnrollmentToken('admin', 60);
    dbService.upsertPendingNode({
      id: 'node-jetson-pending-01',
      token,
      hostname: 'jetson-orin-01',
      ip_address: '192.168.1.120',
      arch: 'aarch64',
      ram_total_gb: 31.2,
      ram_free_gb: 27.5,
      disk_free_gb: 840.0,
      gpu_info: 'NVIDIA Orin (Ampere, 1024 CUDA cores)'
    });

    const pending = dbService.getPendingNodes();
    assert.equal(pending.length, 1);
    assert.equal(pending[0].hostname, 'jetson-orin-01');
    assert.equal(pending[0].status, 'pending_approval');

    // Approve node
    dbService.approvePendingNode('node-jetson-pending-01', 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf', 'Field Sentinel Alpha');
    const node = dbService.getPendingNode('node-jetson-pending-01');
    assert.equal(node?.status, 'approved');
    assert.equal(node?.selected_model, 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf');
    assert.equal(node?.target_node_name, 'Field Sentinel Alpha');

    // Update progress
    dbService.updatePendingNodeProgress('node-jetson-pending-01', 75.0, 'LOADING_DOCKER_IMAGE');
    const inProgress = dbService.getPendingNode('node-jetson-pending-01');
    assert.equal(inProgress?.progress_percent, 75.0);

    // Complete deployment
    dbService.completePendingNode('node-jetson-pending-01', 'http://192.168.1.120:5150');
    assert.equal(dbService.getPendingNodes().length, 0);

    const activeNode = dbService.getNode('node-jetson-pending-01');
    assert.ok(activeNode);
    assert.equal(activeNode?.name, 'Field Sentinel Alpha');
    assert.equal(activeNode?.ip_address, 'http://192.168.1.120:5150');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --experimental-strip-types --test control_center/tests/enrollment-db.test.ts`
Expected: FAIL with `dbService.createEnrollmentToken is not a function`.

- [ ] **Step 3: Implement database schema and methods in `control_center/src/lib/db.ts`**

Add `enrollment_tokens` and `pending_nodes` tables to `initSchema`, and add helper methods:
```ts
export interface PendingNodeRecord {
  id: string;
  token: string;
  hostname: string;
  ip_address: string;
  arch: string;
  ram_total_gb: number;
  ram_free_gb: number;
  disk_free_gb: number;
  gpu_info?: string | null;
  status: 'pending_approval' | 'approved' | 'streaming' | 'failed' | 'completed';
  selected_model?: string | null;
  target_node_name?: string | null;
  progress_percent: number;
  progress_status?: string | null;
  last_heartbeat: string;
  created_at: string;
}
```

Implement in `dbService`:
- `createEnrollmentToken(createdBy, expiryMinutes)`
- `validateEnrollmentToken(token)`
- `claimEnrollmentToken(token)`
- `upsertPendingNode(data)`
- `getPendingNodes()`
- `getPendingNode(id)`
- `approvePendingNode(id, model, name)`
- `updatePendingNodeProgress(id, percent, status)`
- `completePendingNode(id, endpointUrl)`
- `deletePendingNode(id)`

- [ ] **Step 4: Run test to verify it passes**

Run: `node --experimental-strip-types --test control_center/tests/enrollment-db.test.ts`
Expected: PASS (2 tests pass).

- [ ] **Step 5: Commit**

```bash
git add control_center/src/lib/db.ts control_center/tests/enrollment-db.test.ts
git commit -m "feat(c2): add enrollment token and pending nodes SQLite schema and service"
```

---

### Task 2: C2 Enrollment & Stream Depot API Endpoints

**Files:**
- Create: `control_center/src/app/api/fleet/enroll/token/route.ts`
- Create: `control_center/src/app/api/fleet/enroll/register/route.ts`
- Create: `control_center/src/app/api/fleet/enroll/pending/route.ts`
- Create: `control_center/src/app/api/fleet/enroll/approve/route.ts`
- Create: `control_center/src/app/api/fleet/enroll/heartbeat/route.ts`
- Create: `control_center/src/app/api/fleet/enroll/complete/route.ts`
- Create: `control_center/src/app/api/fleet/dist/image/route.ts`
- Create: `control_center/src/app/api/fleet/dist/models/[filename]/route.ts`
- Test: `control_center/tests/enrollment-api.test.ts`

- [ ] **Step 1: Write integration tests for enrollment API endpoints**

Create `control_center/tests/enrollment-api.test.ts`:
```ts
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

const BASE_URL = process.env.C2_TEST_URL || 'http://localhost:5200';

describe('C2 Fleet Enrollment & Stream Depot API Endpoints', () => {
  let createdToken: string;
  let testNodeId = `pending-test-${Date.now()}`;

  it('POST /api/fleet/enroll/token generates a single-use token and command snippet', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expiry_minutes: 60 })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    assert.ok(data.token);
    assert.ok(data.docker_command.includes(data.token));
    createdToken = data.token;
  });

  it('POST /api/fleet/enroll/register registers a new phoned-home node', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: testNodeId,
        token: createdToken,
        hostname: 'field-orin-unit',
        ip_address: '192.168.1.99',
        arch: 'aarch64',
        ram_total_gb: 16.0,
        ram_free_gb: 12.5,
        disk_free_gb: 256.0,
        gpu_info: 'NVIDIA Orin Nano'
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
  });

  it('GET /api/fleet/enroll/pending lists the node awaiting approval', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/pending`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    const node = data.pending_nodes.find((n: any) => n.id === testNodeId);
    assert.ok(node);
    assert.equal(node.arch, 'aarch64');
  });

  it('POST /api/fleet/enroll/approve approves the node with target model', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: testNodeId,
        selected_model: 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf',
        target_name: 'Edge Sentinel Unit 99'
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
  });

  it('GET /api/fleet/enroll/heartbeat returns DEPLOY command to bootstrap agent', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/heartbeat?node_id=${testNodeId}`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.action, 'DEPLOY');
    assert.equal(data.selected_model, 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf');
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `node --experimental-strip-types --test control_center/tests/enrollment-api.test.ts`
Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implement enrollment routes and distribution depot endpoints**

1. Create `control_center/src/app/api/fleet/enroll/token/route.ts`
2. Create `control_center/src/app/api/fleet/enroll/register/route.ts`
3. Create `control_center/src/app/api/fleet/enroll/pending/route.ts`
4. Create `control_center/src/app/api/fleet/enroll/approve/route.ts`
5. Create `control_center/src/app/api/fleet/enroll/heartbeat/route.ts`
6. Create `control_center/src/app/api/fleet/enroll/complete/route.ts`
7. Create `control_center/src/app/api/fleet/dist/image/route.ts`:
   - Checks authorized token.
   - Streams `images/krokbot_agent.tar.gz` or dynamically reads exported container image.
8. Create `control_center/src/app/api/fleet/dist/models/[filename]/route.ts`:
   - Validates filename, checks `./models/${filename}`, streams with `Content-Range` and `Accept-Ranges: bytes`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --experimental-strip-types --test control_center/tests/enrollment-api.test.ts`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add control_center/src/app/api/fleet/enroll control_center/src/app/api/fleet/dist control_center/tests/enrollment-api.test.ts
git commit -m "feat(c2): implement enrollment lifecycle and image/model streaming distribution endpoints"
```

---

### Task 3: Lightweight Bootstrap Agent (`krokbot-bootstrap`)

**Files:**
- Create: `krokbot_bootstrap/Dockerfile`
- Create: `krokbot_bootstrap/bootstrap.py`
- Create: `krokbot_bootstrap/entrypoint.sh`
- Create: `krokbot_bootstrap/README.md`

- [ ] **Step 1: Write `bootstrap.py` orchestration script**

Implements:
1. Docker socket verification (`/var/run/docker.sock`).
2. Hardware profiling (`platform.machine()`, `os.uname()`, `/proc/meminfo`, `shutil.disk_usage`).
3. Outbound phone-home to `$C2_URL/api/fleet/enroll/register`.
4. Polling loop to `$C2_URL/api/fleet/enroll/heartbeat`.
5. Streaming image payload into `docker load` via subprocess pipe.
6. Streaming GGUF model directly to `/host_opt_krokbot/models/`.
7. Spawning `krokbot_agent` container via Docker CLI with port mappings (`5150`, `5155`, `8992`).
8. Probing `http://localhost:5150/api/agent/info` for healthy status.
9. Notifying C2 via `POST /api/fleet/enroll/complete`.

- [ ] **Step 2: Create `krokbot_bootstrap/Dockerfile`**

```dockerfile
FROM alpine:3.20

RUN apk add --no-cache python3 py3-pip curl jq docker-cli ca-certificates

WORKDIR /app
COPY bootstrap.py /app/bootstrap.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
```

- [ ] **Step 3: Verify bootstrap script unit execution in local test**

Run: `python krokbot_bootstrap/bootstrap.py --dry-run`
Expected: Validates hardware detection, socket check, and displays formatted terminal output.

- [ ] **Step 4: Commit**

```bash
git add krokbot_bootstrap/
git commit -m "feat(bootstrap): implement lightweight edge bootstrap container for remote docker orchestration"
```

---

### Task 4: Manual Air-Gapped Deployment Bundle & Scripts

**Files:**
- Create: `scripts/package_offline_node.sh`
- Create: `scripts/offline_bundle/install.sh`
- Create: `scripts/offline_bundle/install.ps1`
- Create: `scripts/offline_bundle/README_ENGINEER.md`
- Test: `tests/test_offline_packaging.py`

- [ ] **Step 1: Create `install.sh` automated bash installer**

```bash
#!/usr/bin/env bash
set -e
echo "======================================================"
echo "  KrokBot Air-Gapped Edge Node Offline Installer"
echo "======================================================"

# 1. Check Docker daemon
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running or current user lacks docker group permissions."
  echo "Fix: sudo systemctl start docker && sudo usermod -aG docker \$USER"
  exit 1
fi

# 2. Load Container Image
IMAGE_FILE=$(find images -name "*.tar" -o -name "*.tar.gz" | head -n 1)
if [ -n "$IMAGE_FILE" ]; then
  echo "[1/3] Loading Docker image from $IMAGE_FILE..."
  docker load -i "$IMAGE_FILE"
fi

# 3. Provision Persistent Storage
echo "[2/3] Provisioning persistent storage at /opt/krokbot..."
sudo mkdir -p /opt/krokbot/models /opt/krokbot/data
if ls models/*.gguf >/dev/null 2>&1; then
  sudo cp models/*.gguf /opt/krokbot/models/
fi

# 4. Launch Container
echo "[3/3] Starting KrokBot Agent container..."
docker rm -f krokbot_agent >/dev/null 2>&1 || true
docker run -d --name krokbot_agent --restart unless-stopped \
  -p 5150:5150 -p 5155:5155 -p 8992:8992 \
  -v /opt/krokbot/models:/app/models \
  -v /opt/krokbot/data:/app/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  krokbot_agent:latest

echo "SUCCESS: KrokBot Agent is active on http://localhost:5150"
```

- [ ] **Step 2: Create `install.ps1` for Windows / Docker Desktop environments**
- [ ] **Step 3: Create `package_offline_node.sh` packaging utility**
- [ ] **Step 4: Create unit test `tests/test_offline_packaging.py` verifying package scripts and syntax**
- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_offline_packaging.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/ tests/test_offline_packaging.py
git commit -m "feat(offline): create air-gapped offline deployment bundle scripts and packaging utility"
```

---

### Task 5: Command Center UI — "+ Enroll / Deploy Node" Modal & Pending Approval Queue

**Files:**
- Modify: `control_center/src/app/page.tsx`
- Test: `control_center/tests/c2-api-endpoints.test.ts`

- [ ] **Step 1: Add state and polling for Pending Nodes in `control_center/src/app/page.tsx`**

```tsx
const [pendingNodes, setPendingNodes] = useState<any[]>([]);
const [enrollModalOpen, setEnrollModalOpen] = useState(false);
const [enrollTab, setEnrollTab] = useState<'automated' | 'manual'>('automated');
const [generatedToken, setGeneratedToken] = useState<string | null>(null);
const [generatedCommand, setGeneratedCommand] = useState<string | null>(null);
const [approvingNodeId, setApprovingNodeId] = useState<string | null>(null);
const [selectedDeployModel, setSelectedDeployModel] = useState<Record<string, string>>({});
const [customDeployNames, setCustomDeployNames] = useState<Record<string, string>>({});
```

- [ ] **Step 2: Add `fetchPendingNodes` to polling interval**
- [ ] **Step 3: Add "Pending Nodes (Approval Required)" banner & cards above active fleet cards**
- [ ] **Step 4: Add "+ Enroll / Deploy Node" header button and tabbed interactive modal**
  - Tab 1: Automated C2 Push (Token generator, 1-click clipboard copy, runbook link)
  - Tab 2: Manual / Air-Gapped Load (Offline USB instructions & bundle download link)
- [ ] **Step 5: Verify UI build and run Next.js tests**

Run: `npm test` in `control_center/`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add control_center/src/app/page.tsx
git commit -m "feat(ui): add node enrollment modal and pending approval queue to command center"
```

---

### Task 6: Field Engineer Runbook Documentation & End-to-End Verification

**Files:**
- Create: `docs/DEPLOYMENT_ENGINEER_RUNBOOK.md`

- [ ] **Step 1: Write `docs/DEPLOYMENT_ENGINEER_RUNBOOK.md`**
  - Section 1: Pre-flight checklist (Docker daemon, systemd, user permissions)
  - Section 2: Platform-specific guides (NVIDIA Jetson Orin JetPack 5/6, Ubuntu/Debian Linux, Windows WSL2)
  - Section 3: Automated C2 Deployment walkthrough
  - Section 4: Air-Gapped Offline USB Deployment walkthrough
  - Section 5: Diagnostic & troubleshooting FAQ (port conflicts, memory constraints, socket permissions)
- [ ] **Step 2: Run full automated test suites across both repositories**
  - `npm test` in `control_center/`
  - `pytest -v` in root `krokbot/`
- [ ] **Step 3: Commit and Push**

```bash
git add docs/DEPLOYMENT_ENGINEER_RUNBOOK.md
git commit -m "docs: publish field deployment engineer runbook"
git push origin control_v2_enhancements
```

---
