# Design Spec: Persistent Sandbox Workspace & Automated Code Execution for KrokBot

**Date**: 2026-09-10  
**Author**: Antigravity AI  
**Status**: Draft for User Approval  

---

## 1. Executive Summary

This design enables **persistent sandbox workspace operations, Python script generation, script execution, and file inspection** within KrokBot. When users prompt KrokBot to write, run, or debug scripts (e.g., creating `./reconcile.py` and reading `report.txt`), KrokBot automatically generates the Python script, saves it to `data/sandbox_workspace/`, executes it inside the sandbox environment, reads any created report/output files, and reports the exact exit code and file contents back to the user.

---

## 2. Key Capabilities & Requirements

1. **Persistent Sandbox Workspace (`data/sandbox_workspace/`)**:
   - Create and maintain `data/sandbox_workspace/` for storing scripts and generated artifacts.
   - `SandboxExecutor` methods:
     - `write_file(filename: str, content: str)`: Saves script/data file to `data/sandbox_workspace/`.
     - `read_file(filename: str)`: Reads output file (e.g. `report.txt`).
     - `execute_file(filename: str)`: Runs Python script inside `data/sandbox_workspace/` with `cwd=workspace_dir`.
     - `execute_script(code: str, filename: Optional[str])`: Writes code to workspace file and executes it.

2. **Coding & Scripting Intent Detection in `KrokBotAgent`**:
   - Detect coding keywords (`script`, `python`, `.py`, `code`, `reconcile`, `csv`, `generate script`, `write a script`).
   - Multi-step execution pipeline:
     1. **Code Generation**: Prompt LLM to output full executable Python script.
     2. **Script Persistence**: Write script (e.g. `reconcile.py`) to `data/sandbox_workspace/`.
     3. **Sandbox Execution**: Run script via `SandboxExecutor.execute_file("reconcile.py")` in workspace.
     4. **Artifact Inspection**: Automatically read generated output files (`report.txt`) if created.
     5. **Response Synthesis**: Synthesize report showing code, sandbox stdout/stderr, exit code, and generated `report.txt` content.

---

## 3. Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                       User Request                          │
│  "Create a Python script at ./reconcile.py ..."             │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                      KrokBotAgent                           │
│  1. Intent Router -> "scripting"                            │
│  2. Generate Python Code -> extract ```python block         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                     SandboxExecutor                         │
│  1. Save code to 'data/sandbox_workspace/reconcile.py'      │
│  2. Run python reconcile.py (cwd='data/sandbox_workspace')  │
│  3. Capture exit code, stdout, stderr                       │
│  4. Read 'data/sandbox_workspace/report.txt'                │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Final Answer                           │
│  - Script Created & Executed                                │
│  - Exit Code: 1 (or 0)                                      │
│  - Contents of report.txt                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Verification Plan

* **Unit Tests**:
  - `tests/test_sandbox.py`: Test `write_file`, `read_file`, `execute_file` in persistent workspace.
  - `tests/test_agent_scripting.py`: Test end-to-end `reconcile.py` prompt execution flow.
* **Manual Verification**:
  - Run user's exact `reconcile.py` prompt.
  - Verify `data/sandbox_workspace/reconcile.py`, `ledger_a.csv`, `ledger_b.csv`, and `report.txt` are created.
  - Verify exit code (1 due to discrepancy) and `report.txt` content are printed clearly.

---
