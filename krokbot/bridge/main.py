from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
from krokbot.bridge.metrics import get_system_summary, get_storage_info, get_services_list
from krokbot.bridge.schemas import SystemSummary, StoragePartition, ServiceItem
from typing import List, Dict, Any, Optional

import subprocess
from krokbot.config.tools_config import get_tools_manager

app = FastAPI(title="KrokBot Host API Bridge", version="1.0.0")

scheduler_manager_ref: Optional[Any] = None

def set_scheduler_manager(manager):
    global scheduler_manager_ref
    scheduler_manager_ref = manager

# ---------------------------------------------------------
# Host Hardware Telemetry Endpoints (Gated by 'os_bridge')
# ---------------------------------------------------------
@app.get("/api/v1/system/summary", response_model=SystemSummary)
def system_summary():
    tools_mgr = get_tools_manager()
    if not tools_mgr.is_tool_enabled("os_bridge"):
        raise HTTPException(
            status_code=403,
            detail="[SECURITY GOVERNANCE ERROR] 'OS Bridge (Host Hardware)' tool is disabled by administrator policy in agent_tools.json. Host hardware telemetry is denied."
        )
    return get_system_summary()

@app.get("/api/v1/system/storage", response_model=List[StoragePartition])
def storage_info():
    tools_mgr = get_tools_manager()
    if not tools_mgr.is_tool_enabled("os_bridge"):
        raise HTTPException(
            status_code=403,
            detail="[SECURITY GOVERNANCE ERROR] 'OS Bridge (Host Hardware)' tool is disabled by administrator policy in agent_tools.json. Host hardware telemetry is denied."
        )
    return get_storage_info()

@app.get("/api/v1/services/list", response_model=List[ServiceItem])
def services_list():
    tools_mgr = get_tools_manager()
    if not tools_mgr.is_tool_enabled("os_bridge"):
        raise HTTPException(
            status_code=403,
            detail="[SECURITY GOVERNANCE ERROR] 'OS Bridge (Host Hardware)' tool is disabled by administrator policy in agent_tools.json. Host hardware telemetry is denied."
        )
    return get_services_list()

# ---------------------------------------------------------
# Host OS CLI Execution Endpoint (Gated by 'system_cli')
# ---------------------------------------------------------
@app.post("/api/v1/system/cli")
def execute_system_cli(payload: Dict[str, Any]):
    tools_mgr = get_tools_manager()
    if not tools_mgr.is_tool_enabled("system_cli"):
        raise HTTPException(
            status_code=403,
            detail="[SECURITY GOVERNANCE ERROR] 'System CLI Functions (Host OS)' tool is disabled by administrator policy in agent_tools.json. Host OS CLI execution is blocked."
        )
    command = payload.get("command", "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command must not be empty.")
    
    timeout = payload.get("timeout", 30)
    try:
        import sys
        import os
        import re

        if sys.platform == "win32":
            # On Windows, execute via PowerShell to natively support PowerShell cmdlets, scripts, and Win32 binaries
            ps_match = re.match(r'^(?:powershell(?:\.exe)?|pwsh(?:\.exe)?)\s+(?:-[a-zA-Z]+\s+)*-(?:c|command)\s+(.*)$', command, flags=re.IGNORECASE | re.DOTALL)
            if ps_match:
                script_body = ps_match.group(1).strip()
                if (script_body.startswith('"') and script_body.endswith('"')) or (script_body.startswith("'") and script_body.endswith("'")):
                    if script_body.count(script_body[0]) == 2:
                        script_body = script_body[1:-1]
                proc = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script_body],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace"
                )
            else:
                proc = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace"
                )
        else:
            # On Linux / macOS, execute via bash or sh
            shell_bin = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
            proc = subprocess.run(
                [shell_bin, "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )

        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": command
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "stdout": "",
            "stderr": f"Host command timed out after {timeout} seconds.",
            "command": command
        }
    except Exception as e:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Error executing host CLI: {str(e)}",
            "command": command
        }

# ---------------------------------------------------------
# Agent Tools Governance & Central C2 Management Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/tools")
def get_tools_policy():
    """Retrieve full agent tools policy configuration for C2 review."""
    tools_mgr = get_tools_manager()
    return tools_mgr.load_config()

@app.put("/api/v1/tools")
def update_tools_policy(payload: Dict[str, Any]):
    """Update agent tools enablement policy via remote central management API."""
    tools_mgr = get_tools_manager()
    updated = tools_mgr.update_tools_policy(payload, updated_by="central_c2_api")
    return {"status": "success", "config": updated}

@app.post("/api/v1/tools/{tool_id}/toggle")
def toggle_tool_status(tool_id: str, payload: Dict[str, Any]):
    """Toggle a specific tool on or off."""
    tools_mgr = get_tools_manager()
    enabled = payload.get("enabled", True)
    try:
        updated = tools_mgr.set_tool_enabled(tool_id, enabled, updated_by="bridge_api")
        return {"status": "success", "tool_id": tool_id, "enabled": enabled, "config": updated}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/v1/tools/reset")
def reset_tools_policy():
    """Reset tools policy to system defaults."""
    tools_mgr = get_tools_manager()
    updated = tools_mgr.reset_to_defaults(updated_by="bridge_api_reset")
    return {"status": "success", "config": updated}

# Remote Schedule Management Endpoints
@app.get("/api/v1/schedules")
def list_schedules_bridge():
    if scheduler_manager_ref:
        return scheduler_manager_ref.get_all_schedules()
    return []

@app.get("/api/v1/schedules/refresh")
def refresh_schedules_bridge():
    if scheduler_manager_ref:
        return {
            "status": "success",
            "schedules": scheduler_manager_ref.reload_schedules()
        }
    return {"status": "error", "message": "Scheduler manager not initialized", "schedules": []}

@app.post("/api/v1/schedules")
def create_schedule_bridge(payload: Dict[str, Any]):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    name = payload.get("name", "Scheduled Health Task")
    cron_expr = payload.get("cron_expression", "0 * * * *")
    prompt = payload.get("prompt", "Check system health")
    item = scheduler_manager_ref.add_schedule(name, cron_expr, prompt)
    return item

@app.delete("/api/v1/schedules/{schedule_id}")
def delete_schedule_bridge(schedule_id: str):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    success = scheduler_manager_ref.remove_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return {"status": "success", "deleted_id": schedule_id}

@app.post("/api/v1/schedules/{schedule_id}/delete")
def delete_schedule_bridge_post(schedule_id: str):
    return delete_schedule_bridge(schedule_id)

@app.post("/api/v1/schedules/{schedule_id}/run")
def run_schedule_bridge_post(schedule_id: str):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    result = scheduler_manager_ref.trigger_schedule(schedule_id, source="bridge_api")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return {
        "status": "success",
        "triggered": result,
        "execution": result.get("execution", {})
    }

@app.get("/api/v1/schedules/executions")
def get_all_executions_bridge(limit: int = 100):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    return {
        "status": "success",
        "executions": scheduler_manager_ref.get_all_executions(limit=limit)
    }

@app.get("/api/v1/schedules/{schedule_id}/executions")
def get_job_executions_bridge(schedule_id: str, limit: int = 50):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    return {
        "status": "success",
        "schedule_id": schedule_id,
        "executions": scheduler_manager_ref.get_job_executions(schedule_id, limit=limit)
    }

@app.get("/api/v1/schedules/executions/{execution_id}")
def get_single_execution_bridge(execution_id: str):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    record = scheduler_manager_ref.get_execution_by_id(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Execution record '{execution_id}' not found")
    return {
        "status": "success",
        "execution": record
    }

# ---------------------------------------------------------
# Remote Script Assets Management Endpoints (Central C2)
# ---------------------------------------------------------
from krokbot.scripts.manager import get_script_manager

@app.get("/api/v1/scripts")
def list_scripts_bridge():
    """List all saved script assets with metadata and documentation summaries."""
    mgr = get_script_manager()
    return mgr.list_scripts()

@app.get("/api/v1/scripts/{name}")
def get_script_bridge(name: str):
    """Retrieve full script code and paired markdown documentation."""
    mgr = get_script_manager()
    script = mgr.get_script(name)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script asset '{name}' not found")
    return script

@app.post("/api/v1/scripts")
def create_script_bridge(payload: Dict[str, Any]):
    """Save or register a script asset with code and paired markdown via C2."""
    mgr = get_script_manager()
    name = payload.get("name") or payload.get("filename")
    code = payload.get("code")
    if not name or not code:
        raise HTTPException(status_code=400, detail="Name and code are required")
    purpose = payload.get("purpose")
    markdown = payload.get("markdown")
    category = payload.get("category", "General Automation")
    res = mgr.save_script(name=name, code=code, purpose=purpose, markdown_content=markdown, category=category, author="central_c2_api")
    return res

@app.delete("/api/v1/scripts/{name}")
@app.post("/api/v1/scripts/{name}/delete")
def delete_script_bridge(name: str):
    """Delete a script asset and its paired markdown file via C2."""
    mgr = get_script_manager()
    deleted = mgr.delete_script(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Script asset '{name}' not found")
    return {"status": "success", "deleted": name}

@app.post("/api/v1/scripts/{name}/run")
def run_saved_script_bridge(name: str):
    """Execute a saved script asset in the compute sandbox via C2."""
    mgr = get_script_manager()
    from krokbot.sandbox.executor import SandboxExecutor
    sandbox = SandboxExecutor()
    res = mgr.run_script(name, sandbox)
    return res

@app.get("/api/v1/scripts/{name}/stream")
@app.post("/api/v1/scripts/{name}/stream")
def stream_saved_script_bridge(name: str):
    """Stream real-time terminal execution events for a saved script asset via Server-Sent Events (SSE)."""
    mgr = get_script_manager()
    from krokbot.sandbox.executor import SandboxExecutor
    sandbox = SandboxExecutor()

    def event_generator():
        for item in mgr.run_script_stream(name, sandbox):
            payload = json.dumps(item)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/v1/models/{filename}/activate")
def activate_model_bridge(filename: str):
    """Set active inference model via C2 API."""
    from krokbot.model_manager import set_active_model
    try:
        return set_active_model(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate model: {e}")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("BRIDGE_PORT", "8992"))
    print(f"============================================================")
    print(f"  KrokBot Host API Bridge - Native Host Telemetry & CLI")
    print(f"============================================================")
    print(f"  Port:      http://0.0.0.0:{port}")
    print(f"  Platform:  {sys.platform}")
    print(f"============================================================")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")



