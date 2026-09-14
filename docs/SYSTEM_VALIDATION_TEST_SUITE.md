# KrokBot System Validation & Operational Test Runbook

This document provides a set of numbered, reproducible operational validation tests to verify the core capabilities of the KrokBot ecosystem: autonomous script generation, self-healing sandbox verification, cron scheduling, primary-to-worker multi-agent delegation, and fleet control.

---

## 1. Quick Reference & System Access

| Service | Address | Primary Function |
|---|---|---|
| **KrokBot C2 (Control Center)** | `http://localhost:5200` | Multi-agent fleet manager, node accordions, agent command dispatcher, audit logs |
| **Primary Sentinel Agent (`krok-prime-01`)** | `http://localhost:5150` | Primary interactive console, script manager, cron scheduler, tool policy manager |
| **Shared Llama.cpp Inference Arbiter** | `http://127.0.0.1:5155` | Central GPU/CPU inference server shared across all co-located agents |
| **Host OS Bridge (Optional)** | `http://localhost:8992` | Host CLI command proxy (PowerShell / Bash execution outside container) |

---

## 2. Test Catalog

```
[TEST 01] Autonomous Script Generation -> Sandbox Testing -> Automated Cron Placement
[TEST 02] Primary Sentinel Orchestration & Instructing Worker Agents (Multi-Agent Swarm)
[TEST 03] Script Manager Upload, Dependency Verification & Execution
[TEST 04] Security Policy Governance & Execution Blocking
[TEST 05] Dynamic In-Container Model Hot-Swapping (Inference Arbiter)
[TEST 06] Real-Time Fleet Telemetry, Worker Lifecycle & Historical Audit Logging
```

---

## TEST 01: Autonomous Script Generation, Sandbox Testing & Automated Cron Placement

### Objective
Verify that an agent can deconstruct a natural language instruction, write a self-contained Python script, save it to its isolated workspace, verify execution in the sandbox with self-healing retry, and deploy it to the internal cron scheduler.

### Pre-conditions
- Primary Sentinel (`krok-prime-01`) is running on `http://localhost:5150` or C2 at `http://localhost:5200`.
- Python Scripting and Sandbox CLI tools are enabled in the Agent Tools policy manager.

### Test Procedure

#### Step 1: Dispatch Sequenced Instruction
In either the **C2 Autonomous Agent Command Console** (`http://localhost:5200`) or the **Agent Console** (`http://localhost:5150`), enter the following multi-step prompt:

```text
Step 1: Write and verify a Python script named system_health_monitor.py that checks memory usage and writes a summary report to report.txt.
Step 2: Once verified with exit code 0, schedule this script in cron to execute every 2 minutes.
```

*(Alternatively, single-sentence prompt)*:
```text
Create a python script named system_health_monitor.py that audits system memory and disk, verify it runs cleanly, and then schedule it in cron every 2 minutes.
```

#### Step 2: Observe Autonomous Execution Flow
The agent's `WorkflowPlanner` detects a sequenced multi-step request and executes:
1. **Script Synthesis**: Generates `system_health_monitor.py` inside `/app/workspaces/agent_krok-prime-01/`.
2. **Sandbox Execution**: Runs `python system_health_monitor.py`. If errors occur, the agent's self-healing loop refines the code automatically.
3. **Cron Registration**: Registers the task with schedule `*/2 * * * *` targeting `system_health_monitor.py`.

#### Step 3: Verification & Acceptance Criteria
- [ ] **Console Output**: Terminal displays:
  - `[AGENT WORKFLOW] Starting Sequenced Execution`
  - `Generating & Testing system_health_monitor.py in Sandbox`
  - `Script ./system_health_monitor.py executed successfully in sandbox (exit code 0)`
  - `Deploying verified script to Cron Scheduler`
  - `Schedule created: */2 * * * *`
- [ ] **File Inspection**: Verify `system_health_monitor.py` exists in `/app/workspaces/agent_krok-prime-01/` and `report.txt` was created with exit code 0.
- [ ] **Cron Table UI**: Navigate to `http://localhost:5150` > **Scheduled Tasks** tab. Confirm the new job appears with:
  - Name: `Scheduled Task` (or `system_health_monitor.py`)
  - Cron: `*/2 * * * *`
  - Target Script: `system_health_monitor.py`
  - Status: `Active`
- [ ] **Execution Tick**: Wait 2 minutes. Observe the Cron Task row's `Last Run` timestamp update and audit log record the automated run.

---

## TEST 02: Primary Sentinel Orchestration & Instructing Worker Agents

### Objective
Verify that the Primary Sentinel (`krok-prime-01`) can act as a coordinator to instruct and delegate tasks to secondary worker agents (`krok-worker-02`, etc.) running in isolated workspaces within the same container.

### Pre-conditions
- Master container `node-jetson-primary` is online at `http://localhost:5200`.
- Primary Sentinel (`krok-prime-01`, Port 5150) is active.

### Test Procedure

#### Step 1: Deploy a Worker Agent (if not already present)
1. On `http://localhost:5200`, expand the `node-jetson-primary` tab.
2. Click **+ Deploy** on the summary line.
3. In the modal, leave default ID `krok-worker-02` and Name `KrokBot Recon Subagent 02`.
4. Click **Deploy Agent Now**.
5. Confirm `krok-worker-02` appears in the expandable agents list with status `RUNNING` on allocated port (e.g., `5151`).

#### Step 2: Instruct Worker Agent via Primary Sentinel
In the C2 Command Console or via Primary Sentinel API, issue a delegation prompt instructing the primary agent to command worker 02:

**Input Prompt to Primary Sentinel (`krok-prime-01`)**:
```text
Instruct worker agent krok-worker-02 on port 5151 to generate a network scan summary script named net_scan.py and execute it.
```

*(Alternatively, direct execution via C2 target selector or inline quick prompt)*:
1. In `http://localhost:5200`, expand agent `krok-worker-02`'s drawer.
2. In the **Quick Prompt** input bar, enter:
   ```text
   Generate a Python script named worker_task.py that calculates prime numbers up to 1000 and prints execution time.
   ```
3. Click **RUN ↵**.

#### Step 3: Verification & Acceptance Criteria
- [ ] **Workspace Isolation**:
  - Primary sentinel files remain in `/app/workspaces/agent_krok-prime-01/`.
  - Worker files are generated exclusively in `/app/workspaces/agent_krok-worker-02/worker_task.py`.
- [ ] **Shared Arbiter Concurrency**: Both agents share the central `llama.cpp` arbiter without crashing or colliding on GPU/CPU resources.
- [ ] **Execution Status**: The inline output box in C2 displays the response with status `SUCCESS` and exit code 0.
- [ ] **Audit Trail**: Check C2 **Fleet Audit Log** on the right panel. Verify an audit entry is created for `krok-worker-02` showing task completion and duration.

---

## TEST 03: Script Manager Upload, Dependency Verification & Execution

### Objective
Verify that the operator can upload a custom Python script alongside an optional `requirements.txt`, and that the agent automatically verifies dependencies, checks execution in sandbox, and adds it to the Script Library.

### Pre-conditions
- Access to Agent Console at `http://localhost:5150` > **Python Script Manager** tile.

### Test Procedure

#### Step 1: Prepare Test Script & Requirements
Create a local test script `math_benchmark.py`:
```python
import sys
import math

def calculate_pi(terms=100000):
    pi = 0.0
    for k in range(terms):
        pi += ((4 / (8 * k + 1)) - (2 / (8 * k + 4)) - (1 / (8 * k + 5)) - (1 / (8 * k + 6))) / (16 ** k)
    return pi

print(f"[Math Benchmark] Computed PI: {calculate_pi()}")
print("[Math Benchmark] Status: Success")
sys.exit(0)
```

Optional `requirements.txt`:
```text
# Standard library test; no third-party packages required
```

#### Step 2: Upload Script via Script Manager
1. Navigate to `http://localhost:5150`.
2. Scroll to the **Python Script Manager** tile.
3. Click **Choose File** for the Python Script and select `math_benchmark.py`.
4. Click **Validate & Verify Script**.

#### Step 3: Verification & Acceptance Criteria
- [ ] **Validation Pass**: The system runs a pre-execution dependency inspection (`pip list` / imports check).
- [ ] **Verification Run**: The script is executed in the isolated sandbox.
- [ ] **Execution Modal / Toast**: A success banner or output block shows:
  - Exit Code: `0`
  - Stdout: `[Math Benchmark] Computed PI: 3.14159...`
- [ ] **Library Inclusion**: The script appears in the **Available Script Library** dropdown ready for immediate scheduling or on-demand execution.

---

## TEST 04: Security Policy Governance & Execution Blocking

### Objective
Verify that the Tool Policy Manager enforces strict security boundaries. When a tool is disabled by administrator policy, any agent attempts to invoke it (or scheduled cron runs using it) are immediately blocked with exit code 126.

### Pre-conditions
- Primary Sentinel running on `http://localhost:5150`.

### Test Procedure

#### Step 1: Disable Python Scripting Tool
1. In `http://localhost:5150`, open the **Tool Policy Manager** tab.
2. Toggle the switch for **Python Scripting** to **DISABLED (OFF)**.
3. Click **Save Tool Policies**.

#### Step 2: Attempt Script Execution
In the Agent Console chat, submit:
```text
Run python code to print "Hello World"
```

#### Step 3: Verification & Acceptance Criteria
- [ ] **Policy Enforcement**: Execution is intercepted before running in sandbox.
- [ ] **Error Response**: The response returns exit code `126` with error:
  `[SECURITY GOVERNANCE ERROR] 'Python Scripting' tool is disabled by administrator policy in agent_tools.json. Python code execution is blocked.`
- [ ] **Policy Restore**: Re-enable **Python Scripting** in the Tool Policy Manager and confirm that subsequent script commands succeed.

---

## TEST 05: Dynamic In-Container Model Hot-Swapping

### Objective
Verify that the central inference engine (`llama.cpp`) can hot-swap its active GGUF model without interrupting C2 telemetry or terminating agent workers.

### Pre-conditions
- Multiple `.gguf` model files are downloaded in the `models/` directory (e.g., `qwen3-4b`, `DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf`).
- Node `node-jetson-primary` is online in C2 (`http://localhost:5200`).

### Test Procedure

#### Step 1: Open Model Switcher
1. On `http://localhost:5200`, locate the `node-jetson-primary` summary line.
2. Click **🧠 Model**.
3. Select an alternate model from the available models list (e.g. `DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf`).
4. Click **Activate Model**.

#### Step 2: Observe Reload
The C2 backend calls `POST /api/fleet/nodes/node-jetson-primary/models/{model}/activate`. The in-container arbiter restarts the llama.cpp server with the new model weights.

#### Step 3: Verification & Acceptance Criteria
- [ ] **Modal Closes**: The modal automatically dismisses upon activation.
- [ ] **Summary Line Update**: The `🧠 Model` badge on the collapsed Edge Device summary line immediately reflects the new model filename.
- [ ] **Telemetry Intact**: CPU and RAM meters continue streaming live data without showing node disconnection.
- [ ] **Inference Verification**: Dispatch a test prompt in the Autonomous Agent Command Console:
  ```text
  Who are you and what is your active model architecture?
  ```
  Confirm the model responds coherently using the newly activated weights.

---

## TEST 06: Fleet Telemetry, Worker Lifecycle & Historical Audit Logging

### Objective
Verify that agent lifecycles (deployment, command execution, stopping, and deletion) are accurately reflected in the database and audit trail.

### Pre-conditions
- C2 dashboard open at `http://localhost:5200`.

### Test Procedure

#### Step 1: Test Edge Device Collapse & Expand
1. Click the header summary row of `node-jetson-primary`. Verify it collapses to a single ~52px compact summary line showing CPU, RAM, Model, and Agent count pills.
2. Click **Expand All** in the top bar; verify all nodes expand. Click **Collapse All**; verify all nodes collapse.

#### Step 2: Test Worker Agent Lifecycle
1. Expand `node-jetson-primary`.
2. Locate worker agent `krok-worker-02`.
3. Click **Stop**. Verify its status pill transitions from `RUNNING` to `STOPPED`.
4. Click **🗑️ Remove**. Confirm the browser dialog prompt.
5. Verify the worker is permanently deleted from SQLite (`c2_fleet.db`) and removed from the agent list.
6. Verify the primary agent `krok-prime-01` **does not have a delete button** (protected sentinel).

#### Step 3: Audit Log Verification
1. Inspect the **Real-Time Fleet Audit Log** panel on the bottom-right of `http://localhost:5200`.
2. Confirm each action performed during testing (deploy, command dispatch, stop, delete) has a logged timestamp, agent ID, and execution duration in milliseconds.

---

## TEST 07: Edge Compute SysOps, Process Supervisor, Self-Healing Watchdog & Fleet Command Broadcast

### Objective
Verify the end-to-end edge compute operations suite:
1. Live hardware thermal package telemetry monitoring (`max_temp_c`) with throttling detection.
2. Live process inspection table with protected process flags.
3. Strict prevention of remote termination for protected PIDs (PID 1, sentinel, system init daemons) via `HTTP 403 Forbidden`.
4. Operational system memory trimming (`malloc_trim(0)`) and temporary workspace cache pruning via `🧹 Clean`.
5. Self-Healing Watchdog rule evaluation and interactive policy toggling (Storage Pressure, Thermal Throttling, Worker Memory Leaks, Inference Heartbeat).
6. Fleet-Wide Parallel Command Broadcast across all registered edge compute nodes.

### Pre-conditions
- Master container node `node-jetson-primary` is online at `http://localhost:5200`.
- Primary Sentinel (`krok-prime-01`, Port 5150) and SysOps API are operational.

### Test Procedure

#### Step 1: Verify Hardware SoC Thermals on Node Summary Line
1. Open C2 Dashboard at `http://localhost:5200`.
2. On the `node-jetson-primary` summary line, locate the SoC Thermal Chip: `🌡️ XX.X°C`.
3. Confirm temperature is displayed with 1-decimal precision and nominal styling (`#ffb000`). If simulated or actual thermals cross 75.0°C, verify the badge pulses red.

#### Step 2: Open Live Process Inspector Modal (`⚙️ SysOps`)
1. On the `node-jetson-primary` summary row, click **⚙️ SysOps**.
2. Observe the modal open with title `Edge Process Inspector — NVIDIA Jetson Orin Nano (Primary Node)`.
3. Confirm the process table loads within 500ms displaying:
   - Container processes with PID, Process Name, Memory (RSS MB), and CPU %.
   - System supervisor processes (PID 1) displaying a prominent green `PROTECTED` badge and disabled `System Core` label.
   - Non-critical worker processes displaying an active red `Terminate` button.

#### Step 3: Test Termination Safety Guards (Protected PID 1)
1. In a terminal or API test runner, attempt to remotely terminate PID 1:
   ```bash
   curl -X POST http://localhost:5200/api/fleet/nodes/node-jetson-primary/sysops/processes/1/kill
   ```
2. Confirm the response returns `HTTP 403 Forbidden` with body:
   ```json
   {
     "status": "error",
     "message": "PID 1 is protected by edge safety policy and cannot be terminated."
   }
   ```
3. Close the modal by clicking **Close** or **×**.

#### Step 4: Test Operational System Cleanup (`🧹 Clean`)
1. On the `node-jetson-primary` summary row, click **🧹 Clean**.
2. Confirm memory trimming and temporary cache cleanup executes immediately.
3. Observe confirmation notice displaying recovered memory in MB and pruned temporary file count.

#### Step 5: Verify Self-Healing Watchdog Engine & Policies
1. Expand the `node-jetson-primary` card accordion.
2. In the `🛡️ Self-Healing Watchdog Policies` section, locate the operational policy pills:
   - `Auto-Clean (85% Disk)`
   - `Thermal Guard (75°C)`
   - `Memory Leak Recovery (800MB)`
   - `Inference Heartbeat Watchdog`
3. Click any active policy pill (e.g. `Auto-Clean`). Verify the pill toggles state to `OFF`, updating the watchdog rule in memory.
4. Click the pill again to toggle it back to `ACTIVE`.

#### Step 6: Test Fleet-Wide Command Broadcast Console
1. Scroll down to the **Autonomous Agent Command Console**.
2. In the header toggle bar, click **[ 📡 Fleet Broadcast (All Nodes) ]**.
3. Verify the target dropdowns are replaced by the high-visibility notice:
   `FLEET-WIDE BROADCAST ACTIVE: Your autonomous instruction will be concurrently dispatched to the primary agent on all registered edge nodes.`
4. Verify the dispatch button updates to `BROADCAST TO FLEET 📡`.
5. Enter instruction:
   ```text
   Audit system memory overhead and report disk readiness.
   ```
6. Click **BROADCAST TO FLEET 📡**.
7. Confirm parallel execution completes across all nodes, displaying individual node results and logging separate entries in the C2 Audit Log.

#### Step 7: Verification & Acceptance Criteria
- [ ] **Thermal Chip**: Live SoC thermals stream continuously with nominal/throttling state indicators.
- [ ] **Process Table**: Accurate memory RSS and CPU metrics rendered with sub-second latency.
- [ ] **Process Protection**: Remote kill attempts against PID 1 or core system daemons are rejected with HTTP 403.
- [ ] **Cleanup Action**: Releases fragmented heap using `malloc_trim(0)` and purges temporary files without service disruption.
- [ ] **Watchdog Toggles**: Real-time rule toggles persist and trigger self-healing remediations upon metric breaches.
- [ ] **Fleet Broadcast**: Concurrent dispatch across all nodes verified with parallel execution results.

---

## 3. Automated Validation Test Command Summary

For continuous integration or rapid CLI regression testing, execute:

```powershell
# 1. Run full C2 TypeScript test suite (API endpoints, remote client, SQLite fleet DB, SysOps suite)
cd control_center
npm test

# 2. Run Python agent test suite (scheduler, sandbox, audit logger, tool policy manager, SysOps diagnostics)
cd ..
pytest tests/ -v
```
