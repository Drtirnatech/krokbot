import os
import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
import json
from typing import Dict, Any, Optional

app = FastAPI(title="KrokBot Web Dashboard", version="1.0.0")

scheduler_manager_ref: Optional[Any] = None
agent_instance_ref: Optional[Any] = None

def set_scheduler_manager(manager):
    global scheduler_manager_ref
    scheduler_manager_ref = manager

def set_agent_instance(agent):
    global agent_instance_ref
    agent_instance_ref = agent

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return "<h1>KrokBot OS Agent Console</h1>"

_last_cpu_time = None
_last_check_time = None
_cached_storage_size = {"models_mb": 0.0, "data_mb": 0.0, "last_scan": 0.0}

def get_container_resource_metrics() -> Dict[str, Any]:
    global _last_cpu_time, _last_check_time, _cached_storage_size
    import time
    import shutil
    import psutil

    now = time.time()
    
    # 1. Process & Memory Introspection
    procs = []
    try:
        procs = list(psutil.process_iter(['pid', 'name', 'cpu_times', 'memory_info']))
    except Exception:
        pass

    total_rss_bytes = 0
    total_cpu_time = 0.0
    for p in procs:
        try:
            total_rss_bytes += p.memory_info().rss
            c_times = p.cpu_times()
            total_cpu_time += (c_times.user + c_times.system)
        except Exception:
            pass

    # Read cgroup v2 memory if available for exact container-level accounting
    cgroup_mem_file = "/sys/fs/cgroup/memory.current"
    if os.path.exists(cgroup_mem_file):
        try:
            with open(cgroup_mem_file, "r") as f:
                cgroup_bytes = int(f.read().strip())
                if cgroup_bytes > 0:
                    total_rss_bytes = cgroup_bytes
        except Exception:
            pass

    mem_used_mb = round(total_rss_bytes / (1024 * 1024), 1)
    mem_used_gb = round(total_rss_bytes / (1024 ** 3), 2)
    host_total_mem = psutil.virtual_memory().total
    mem_percent = round((total_rss_bytes / host_total_mem) * 100, 1) if host_total_mem > 0 else 0.0

    # Read cgroup v2 cpu.stat if available for aggregate container CPU accounting
    cgroup_cpu_file = "/sys/fs/cgroup/cpu.stat"
    cgroup_cpu_time = None
    if os.path.exists(cgroup_cpu_file):
        try:
            with open(cgroup_cpu_file, "r") as f:
                for line in f:
                    if line.startswith("usage_usec"):
                        cgroup_cpu_time = int(line.split()[1]) / 1e6
                        break
        except Exception:
            pass

    # Use cgroup aggregate CPU time if available; fallback to sum of all container process CPU times
    active_cpu_time = cgroup_cpu_time if cgroup_cpu_time is not None else total_cpu_time

    # 2. CPU Calculation over time delta (% of total host CPU across all physical/logical cores)
    num_cpus = psutil.cpu_count() or 1
    container_cpu_percent = 0.0
    if _last_cpu_time is not None and _last_check_time is not None:
        elapsed = now - _last_check_time
        if elapsed > 0.2:
            cpu_delta = active_cpu_time - _last_cpu_time
            if cpu_delta >= 0:
                container_cpu_percent = round((cpu_delta / elapsed) / num_cpus * 100, 1)
                container_cpu_percent = max(0.0, min(100.0, container_cpu_percent))

    _last_cpu_time = active_cpu_time
    _last_check_time = now

    # 3. Storage Footprint Calculation (cached every 15s to minimize I/O)
    if (now - _cached_storage_size["last_scan"]) > 15.0 or _cached_storage_size["last_scan"] == 0.0:
        models_dir = os.getenv("MODELS_DIR", "models")
        data_dir = "data"
        
        def calc_dir_mb(d):
            t = 0
            if os.path.exists(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        try:
                            t += os.path.getsize(os.path.join(root, f))
                        except Exception:
                            pass
            return round(t / (1024 * 1024), 1)

        _cached_storage_size["models_mb"] = calc_dir_mb(models_dir)
        _cached_storage_size["data_mb"] = calc_dir_mb(data_dir)
        _cached_storage_size["last_scan"] = now

    models_mb = _cached_storage_size["models_mb"]
    data_mb = _cached_storage_size["data_mb"]
    service_storage_mb = round(models_mb + data_mb, 1)
    service_storage_gb = round(service_storage_mb / 1024, 2)

    app_root = "/app" if os.path.exists("/app") else "."
    disk_info = shutil.disk_usage(app_root)
    disk_used_gb = round((disk_info.total - disk_info.free) / (1024 ** 3), 1)
    disk_total_gb = round(disk_info.total / (1024 ** 3), 1)
    disk_percent = round(((disk_info.total - disk_info.free) / disk_info.total) * 100, 1) if disk_info.total > 0 else 0.0

    is_docker = os.path.exists("/.dockerenv") or os.path.exists("/sys/fs/cgroup/memory.current")

    return {
        "cpu_percent": container_cpu_percent,
        "memory_percent": mem_percent,
        "container": {
            "cpu_percent": container_cpu_percent,
            "memory_used_mb": mem_used_mb,
            "memory_used_gb": mem_used_gb,
            "memory_percent": mem_percent,
            "storage_service_mb": service_storage_mb,
            "storage_service_gb": service_storage_gb,
            "storage_models_mb": models_mb,
            "storage_data_mb": data_mb,
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "disk_percent": disk_percent,
            "process_count": len(procs),
            "is_docker": is_docker,
            "agent_id": getattr(agent_instance_ref, "agent_id", "krok-prime-01"),
            "agent_name": getattr(agent_instance_ref, "agent_name", "KrokBot Prime Sentinel")
        },
        "agent": {
            "id": getattr(agent_instance_ref, "agent_id", "krok-prime-01"),
            "name": getattr(agent_instance_ref, "agent_name", "KrokBot Prime Sentinel")
        }
    }

@app.get("/api/agent/info")
@app.get("/api/v1/agent/info")
def get_agent_info():
    from krokbot.model_manager import load_config
    cfg = load_config()
    cfg_agent = cfg.get("agent", {})
    return {
        "id": getattr(agent_instance_ref, "agent_id", cfg_agent.get("id", "krok-prime-01")),
        "name": getattr(agent_instance_ref, "agent_name", cfg_agent.get("name", "KrokBot Prime Sentinel")),
        "dashboard_port": cfg_agent.get("dashboard_port", 5150),
        "bridge_port": cfg_agent.get("bridge_port", 8990),
        "default_temperature": cfg_agent.get("default_temperature", 0.2)
    }

@app.get("/api/metrics")
@app.get("/api/v1/metrics")
def get_metrics():
    return get_container_resource_metrics()

@app.get("/api/schedules")
@app.get("/api/v1/schedules")
def get_schedules():
    if scheduler_manager_ref:
        return scheduler_manager_ref.get_all_schedules()
    return []

@app.get("/api/schedules/refresh")
@app.get("/api/v1/schedules/refresh")
def refresh_schedules():
    if scheduler_manager_ref:
        return {
            "status": "success",
            "schedules": scheduler_manager_ref.reload_schedules()
        }
    return {"status": "error", "message": "Scheduler manager not initialized", "schedules": []}

@app.post("/api/schedules")
@app.post("/api/v1/schedules")
def create_schedule(payload: Dict[str, Any]):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    name = payload.get("name", "Scheduled Health Task")
    cron_expr = payload.get("cron_expression", "0 * * * *")
    prompt = payload.get("prompt", "Check system health")
    job_fn = agent_instance_ref.run_task if agent_instance_ref else None
    item = scheduler_manager_ref.add_schedule(name, cron_expr, prompt, job_func=job_fn)
    return item

@app.delete("/api/schedules/{schedule_id}")
@app.delete("/api/v1/schedules/{schedule_id}")
def delete_schedule(schedule_id: str):
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    success = scheduler_manager_ref.remove_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return {"status": "success", "deleted_id": schedule_id}

@app.post("/api/schedules/{schedule_id}/delete")
@app.post("/api/v1/schedules/{schedule_id}/delete")
def delete_schedule_post(schedule_id: str):
    """POST alias for deleting schedule (for HTTP clients with restricted DELETE)."""
    return delete_schedule(schedule_id)

@app.post("/api/schedules/{schedule_id}/run")
@app.post("/api/v1/schedules/{schedule_id}/run")
def run_schedule_manually(schedule_id: str):
    """Manually trigger immediate execution of a scheduled task."""
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    result = scheduler_manager_ref.trigger_schedule(schedule_id, source="web_ui")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return {
        "status": "success",
        "triggered": result,
        "execution": result.get("execution", {})
    }

@app.get("/api/schedules/executions")
@app.get("/api/v1/schedules/executions")
def get_all_executions_endpoint(limit: int = 100):
    """Retrieve global execution audit log across all scheduled tasks."""
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    return {
        "status": "success",
        "executions": scheduler_manager_ref.get_all_executions(limit=limit)
    }

@app.get("/api/schedules/{schedule_id}/executions")
@app.get("/api/v1/schedules/{schedule_id}/executions")
def get_job_executions_endpoint(schedule_id: str, limit: int = 50):
    """Retrieve execution history and audit records for a specific scheduled task."""
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    return {
        "status": "success",
        "schedule_id": schedule_id,
        "executions": scheduler_manager_ref.get_job_executions(schedule_id, limit=limit)
    }

@app.get("/api/schedules/executions/{execution_id}")
@app.get("/api/v1/schedules/executions/{execution_id}")
def get_single_execution_endpoint(execution_id: str):
    """Retrieve a single execution audit record by execution ID."""
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    record = scheduler_manager_ref.get_execution_by_id(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Execution record '{execution_id}' not found")
    return {
        "status": "success",
        "execution": record
    }

@app.delete("/api/schedules")
@app.delete("/api/v1/schedules")
def clear_all_schedules():
    if not scheduler_manager_ref:
        raise HTTPException(status_code=500, detail="Scheduler manager not initialized")
    count = scheduler_manager_ref.clear_all_schedules()
    return {"status": "success", "cleared_count": count}

@app.post("/api/chat")
def chat_endpoint(payload: Dict[str, Any]):
    prompt = payload.get("prompt", "")
    save_mode = payload.get("save_mode")
    show_thinking = payload.get("show_thinking", True)
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    if agent_instance_ref:
        result = agent_instance_ref.run_task(prompt, save_mode=save_mode, show_thinking=show_thinking)
        return {
            "status": result.get("status", "success"),
            "prompt": prompt,
            "reply": result.get("clean_report", result.get("report", "")),
            "raw_reply": result.get("raw_report", result.get("report", "")),
            "thinking": result.get("thinking", ""),
            "show_thinking": result.get("show_thinking", show_thinking),
            "metrics": result.get("metrics", {}),
            "sandbox_output": result.get("sandbox_output", {}),
            "requires_confirmation": result.get("requires_confirmation", False),
            "question": result.get("question"),
            "options": result.get("options"),
            "target_filename": result.get("target_filename"),
            "saved_asset": result.get("saved_asset")
        }
    else:
        # Fallback response for standalone testing
        return {
            "status": "success",
            "prompt": prompt,
            "reply": f"KrokBot executed task: '{prompt}'. Workstation health check completed successfully.",
            "raw_reply": f"KrokBot executed task: '{prompt}'. Workstation health check completed successfully.",
            "thinking": "",
            "show_thinking": show_thinking,
            "metrics": {"cpu_percent": 15.0, "memory_percent": 45.0},
            "sandbox_output": {"exit_code": 0, "stdout": "[SANDBOX DIAGNOSTIC] Complete."}
        }

# ---------------------------------------------------------
# Saved Script Assets Management & Remote C2 Endpoints
# ---------------------------------------------------------
from krokbot.scripts.manager import get_script_manager

@app.get("/api/scripts")
@app.get("/api/v1/scripts")
def list_scripts_endpoint():
    """List all saved script assets with metadata and parsed .md summaries."""
    mgr = get_script_manager()
    return mgr.list_scripts()

@app.get("/api/scripts/{name}")
@app.get("/api/v1/scripts/{name}")
def get_script_endpoint(name: str):
    """Retrieve full script code and paired markdown documentation."""
    mgr = get_script_manager()
    script = mgr.get_script(name)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script asset '{name}' not found")
    return script

@app.post("/api/scripts")
@app.post("/api/v1/scripts")
def create_script_endpoint(payload: Dict[str, Any]):
    """Save or register a script asset with code and paired markdown."""
    mgr = get_script_manager()
    name = payload.get("name") or payload.get("filename")
    code = payload.get("code")
    if not name or not code:
        raise HTTPException(status_code=400, detail="Name and code are required")
    purpose = payload.get("purpose")
    markdown = payload.get("markdown")
    category = payload.get("category", "General Automation")
    res = mgr.save_script(name=name, code=code, purpose=purpose, markdown_content=markdown, category=category)
    return res

@app.post("/api/scripts/upload")
@app.post("/api/v1/scripts/upload")
async def upload_script_endpoint(request: Request):
    """
    Upload a Python script and optional requirements.txt.
    Performs AST syntax validation, requirements check (and optional install),
    and test execution verification in the sandbox before saving to data/scripts/.
    """
    mgr = get_script_manager()
    from krokbot.sandbox.executor import SandboxExecutor
    sandbox = SandboxExecutor()

    content_type = request.headers.get("content-type", "")

    filename = ""
    code = ""
    requirements_text = None
    purpose = "Uploaded Python script asset"
    category = "General Automation"
    auto_install = True
    verify_execution = True

    if "application/json" in content_type:
        payload = await request.json()
        filename = payload.get("filename") or payload.get("name") or "script.py"
        code = payload.get("code") or ""
        requirements_text = payload.get("requirements") or payload.get("requirements_text")
        purpose = payload.get("purpose") or purpose
        category = payload.get("category") or category
        auto_install = payload.get("auto_install", True)
        verify_execution = payload.get("verify_execution", True)
    else:
        form = await request.form()
        file_obj = form.get("file")
        if file_obj and hasattr(file_obj, "filename") and hasattr(file_obj, "read"):
            filename = file_obj.filename
            raw_bytes = await file_obj.read()
            code = raw_bytes.decode("utf-8", errors="replace")
        else:
            code = form.get("code", "")
            filename = form.get("filename", "") or form.get("name", "script.py")

        req_obj = form.get("requirements")
        if req_obj and hasattr(req_obj, "read"):
            raw_req = await req_obj.read()
            requirements_text = raw_req.decode("utf-8", errors="replace")
        elif "requirements_text" in form:
            requirements_text = str(form.get("requirements_text"))
        elif "requirements" in form:
            requirements_text = str(form.get("requirements"))

        if form.get("purpose"):
            purpose = str(form.get("purpose"))
        if form.get("category"):
            category = str(form.get("category"))
        if "auto_install" in form:
            auto_install = str(form.get("auto_install")).lower() in ["true", "1", "yes"]
        if "verify_execution" in form:
            verify_execution = str(form.get("verify_execution")).lower() in ["true", "1", "yes"]

    if not filename:
        filename = "script.py"
    if not filename.endswith(".py"):
        filename += ".py"

    if not code or not str(code).strip():
        raise HTTPException(status_code=400, detail="Python script code or file is required")

    # Perform validation and verification
    verification = mgr.validate_and_verify(
        filename=filename,
        code=str(code),
        requirements_content=requirements_text,
        auto_install=auto_install,
        sandbox_executor=sandbox
    )

    # If syntax is broken, reject
    if not verification["valid_syntax"]:
        return JSONResponse(
            status_code=400,
            content={
                "status": "syntax_error",
                "message": verification["error"],
                "verification": verification,
                "name": filename
            }
        )

    # If requirements missing, report
    if not verification["requirements_ok"]:
        return JSONResponse(
            status_code=422,
            content={
                "status": "requirements_missing",
                "message": verification["error"],
                "verification": verification,
                "name": filename
            }
        )

    # Save the script asset
    saved = mgr.save_script(
        name=filename,
        code=str(code),
        purpose=purpose,
        category=category,
        requirements_content=requirements_text,
        verification_info=verification
    )

    return {
        "status": "verified" if verification["execution_verified"] else "saved_unverified",
        "name": saved["name"],
        "filename": saved["filename"],
        "verification": verification,
        "script": saved
    }

@app.delete("/api/scripts/{name}")
@app.delete("/api/v1/scripts/{name}")
@app.post("/api/scripts/{name}/delete")
def delete_script_endpoint(name: str):
    """Delete a script asset and its paired markdown file."""
    mgr = get_script_manager()
    deleted = mgr.delete_script(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Script asset '{name}' not found")
    return {"status": "success", "deleted": name}

@app.post("/api/scripts/{name}/run")
@app.post("/api/v1/scripts/{name}/run")
def run_saved_script_endpoint(name: str):
    """Execute a saved script asset in the compute sandbox."""
    mgr = get_script_manager()
    from krokbot.sandbox.executor import SandboxExecutor
    sandbox = SandboxExecutor()
    res = mgr.run_script(name, sandbox)
    return res

@app.get("/api/scripts/{name}/stream")
@app.post("/api/scripts/{name}/stream")
@app.get("/api/v1/scripts/{name}/stream")
@app.post("/api/v1/scripts/{name}/stream")
def stream_saved_script_endpoint(name: str):
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


@app.get("/api/llamacpp/status")
def get_llamacpp_status():
    from krokbot.agent.llamacpp_client import LlamaCppClient
    from krokbot.model_manager import load_config
    
    if agent_instance_ref and hasattr(agent_instance_ref, "client"):
        client = agent_instance_ref.client
    else:
        client = LlamaCppClient()
    alive = client.is_alive()
    cfg = load_config()
    loaded_models = []
    
    if alive:
        try:
            import httpx
            with httpx.Client(timeout=1.5) as h:
                res = h.get(f"{client.base_url}/v1/models")
                if res.status_code == 200:
                    loaded_models = [m.get("id") for m in res.json().get("data", [])]
        except Exception:
            pass

    return {
        "status": "online" if alive else "offline",
        "base_url": client.base_url,
        "loaded_models": loaded_models,
        "active_model_name": cfg.get("model", {}).get("name", "Unknown"),
        "context_size": cfg.get("model", {}).get("context_size", 2048),
        "chat_format": cfg.get("model", {}).get("chat_format", "chatml")
    }

@app.get("/api/models")
def list_models_endpoint():
    from krokbot.model_manager import load_config, get_available_models
    cfg = load_config()
    available = get_available_models()
    return {
        "available": available,
        "catalog": cfg.get("catalog", {}),
        "active_config": cfg.get("model", {})
    }

@app.delete("/api/models/{filename}")
@app.delete("/api/v1/models/{filename}")
@app.post("/api/models/{filename}/delete")
def delete_model_endpoint(filename: str):
    from krokbot.model_manager import delete_model_file
    try:
        deleted = delete_model_file(filename)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Model file '{filename}' not found in storage directory.")
        
        global _cached_storage_size
        _cached_storage_size["last_scan"] = 0.0

        return {
            "status": "success",
            "message": f"Model file '{filename}' deleted and purged from container storage.",
            "filename": filename
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting model: {str(e)}")

@app.post("/api/models/{filename}/activate")
@app.post("/api/v1/models/{filename}/activate")
def activate_model_endpoint(filename: str):
    """Set the active GGUF inference model and reload the inference engine."""
    from krokbot.model_manager import set_active_model
    try:
        res = set_active_model(filename)
        if agent_instance_ref and hasattr(agent_instance_ref, "client"):
            agent_instance_ref.client.model = res.get("name", filename)
        global _cached_storage_size
        _cached_storage_size["last_scan"] = 0.0
        return res
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate model: {e}")

@app.post("/api/models/download")
def download_model_endpoint(payload: Dict[str, Any]):
    import threading
    from krokbot.model_manager import load_config, download_model_file, find_models_dir, download_state
    
    if download_state.get("status") == "downloading":
        raise HTTPException(status_code=400, detail="A model download is already in progress.")

    cfg = load_config()
    url = payload.get("url", "").strip()
    filename = payload.get("filename", "").strip()
    catalog_key = payload.get("catalog_key", "").strip()

    if catalog_key and catalog_key in cfg.get("catalog", {}):
        cat_item = cfg["catalog"][catalog_key]
        url = cat_item.get("url", url)
        filename = cat_item.get("filename", filename)

    if not url:
        raise HTTPException(status_code=400, detail="Model download URL is required.")
    if not filename:
        filename = url.split("/")[-1].split("?")[0]
        if not filename.endswith(".gguf"):
            filename += ".gguf"

    target_path = os.path.join(find_models_dir(), filename)

    def bg_download():
        download_model_file(url, target_path)

    thread = threading.Thread(target=bg_download, daemon=True)
    thread.start()

    return {
        "status": "started",
        "filename": filename,
        "target_path": target_path
    }

@app.get("/api/models/download/progress")
def download_progress_endpoint():
    from krokbot.model_manager import download_state
    return download_state

@app.post("/api/llamacpp/prompt")
def direct_llamacpp_prompt(payload: Dict[str, Any]):
    import time
    from krokbot.agent.llamacpp_client import LlamaCppClient
    
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    
    system = payload.get("system", "You are a helpful, concise AI assistant.")
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 512))

    client = LlamaCppClient()
    start_t = time.time()
    result = client.chat([
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ], temperature=temperature, max_tokens=max_tokens)
    latency_ms = round((time.time() - start_t) * 1000, 1)

    return {
        "status": "success",
        "reply": result.get("message", {}).get("content", ""),
        "latency_ms": latency_ms,
        "model": client.model
    }

# ---------------------------------------------------------
# Agent Tools Configuration & Remote C2 Governance Endpoints
# ---------------------------------------------------------
from krokbot.config.tools_config import get_tools_manager

@app.get("/api/tools")
@app.get("/api/v1/tools")
def get_tools_policy_endpoint():
    """Returns the agent tools configuration for dashboard UI and remote central C2."""
    tools_mgr = get_tools_manager()
    return tools_mgr.load_config()

@app.put("/api/v1/tools")
@app.post("/api/tools")
def update_tools_policy_endpoint(payload: Dict[str, Any]):
    """Update agent tools configuration from UI or central C2."""
    tools_mgr = get_tools_manager()
    updated = tools_mgr.update_tools_policy(payload, updated_by="web_dashboard_or_c2")
    return {"status": "success", "config": updated}

@app.post("/api/tools/{tool_id}/toggle")
@app.post("/api/v1/tools/{tool_id}/toggle")
def toggle_tool_endpoint(tool_id: str, payload: Dict[str, Any]):
    """Toggle a specific tool on/off with persistent write."""
    tools_mgr = get_tools_manager()
    enabled = payload.get("enabled", True)
    try:
        updated = tools_mgr.set_tool_enabled(tool_id, enabled, updated_by="web_dashboard")
        return {"status": "success", "tool_id": tool_id, "enabled": enabled, "config": updated}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/tools/reset")
@app.post("/api/v1/tools/reset")
def reset_tools_endpoint():
    """Reset tools policy to factory defaults."""
    tools_mgr = get_tools_manager()
    updated = tools_mgr.reset_to_defaults(updated_by="dashboard_reset")
    return {"status": "success", "config": updated}

@app.get("/api/agents")
@app.get("/api/v1/agents")
def list_agents_endpoint():
    """List all agents managed within this container."""
    from krokbot.supervisor import get_supervisor
    sup = get_supervisor()
    return {"status": "success", "agents": sup.list_agents()}

@app.post("/api/agents/deploy")
@app.post("/api/v1/agents/deploy")
def deploy_agent_endpoint(payload: Dict[str, Any]):
    """Deploy a new uniform agent instance inside the running container."""
    from krokbot.supervisor import get_supervisor
    sup = get_supervisor()
    aid = payload.get("id") or payload.get("agent_id")
    name = payload.get("name") or payload.get("agent_name") or f"KrokBot Worker {aid}"
    if not aid:
        raise HTTPException(status_code=400, detail="Agent ID is required.")
    try:
        res = sup.spawn_agent(agent_id=aid, agent_name=name, config_overrides=payload)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deploy agent: {e}")

@app.post("/api/agents/{agent_id}/stop")
@app.post("/api/v1/agents/{agent_id}/stop")
def stop_agent_endpoint(agent_id: str):
    """Stop a spawned agent instance."""
    from krokbot.supervisor import get_supervisor
    sup = get_supervisor()
    success = sup.stop_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot stop agent '{agent_id}' (not found or protected primary agent).")
    return {"status": "success", "message": f"Agent '{agent_id}' stopped."}


def export_health_report(filepath: str, report_content: str, metrics: Dict[str, Any]) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_text = f"""# KrokBot Workstation Health Report

**Generated**: {now}  
**OS Info**: {metrics.get('os_info', 'Unknown OS')}  

---

## System Metrics Baseline
* **CPU Usage**: {metrics.get('cpu_percent', 'N/A')}%
* **Memory Usage**: {metrics.get('memory_percent', 'N/A')}%

---

## Agent Diagnostic Summary

{report_content}

---
*Report generated by KrokBot Autonomous Diagnostic Agent.*
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_text)
