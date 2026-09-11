import pytest
import os
from fastapi.testclient import TestClient
from krokbot.dashboard.server import app, export_health_report

client = TestClient(app)

def test_dashboard_index_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "KrokBot OS" in response.text and "Agent Console" in response.text

def test_schedules_api_endpoints(tmp_path):
    from krokbot.scheduler.manager import CronSchedulerManager
    from krokbot.dashboard.server import set_scheduler_manager
    from krokbot.bridge.main import app as bridge_app, set_scheduler_manager as bridge_set_scheduler_manager
    
    storage_file = tmp_path / "test_schedules.json"
    scheduler = CronSchedulerManager(storage_path=str(storage_file))
    set_scheduler_manager(scheduler)
    bridge_set_scheduler_manager(scheduler)
    
    bridge_client = TestClient(bridge_app)

    # 1. Create a schedule via Dashboard POST
    create_resp = client.post("/api/schedules", json={
        "name": "Hourly Health Audit",
        "cron_expression": "0 * * * *",
        "prompt": "Inspect system health"
    })
    assert create_resp.status_code == 200
    item = create_resp.json()
    sched_id = item["id"]
    assert item["name"] == "Hourly Health Audit"

    # 2. List schedules
    list_resp = client.get("/api/schedules")
    assert list_resp.status_code == 200
    schedules = list_resp.json()
    assert any(s["id"] == sched_id for s in schedules)

    # 3. Refresh schedules
    ref_resp = client.get("/api/schedules/refresh")
    assert ref_resp.status_code == 200
    assert ref_resp.json()["status"] == "success"

    # 4. Trigger / run schedule manually
    run_resp = client.post(f"/api/schedules/{sched_id}/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "success"
    assert "execution" in run_resp.json()
    assert run_resp.json()["execution"]["job_id"] == sched_id

    # 5. Query job execution audit history
    exec_resp = client.get(f"/api/schedules/{sched_id}/executions")
    assert exec_resp.status_code == 200
    assert len(exec_resp.json()["executions"]) >= 1

    # 6. Query global executions
    all_exec_resp = client.get("/api/schedules/executions")
    assert all_exec_resp.status_code == 200
    assert len(all_exec_resp.json()["executions"]) >= 1

    # 7. Remote API mirrored on Host Bridge
    bridge_list = bridge_client.get("/api/v1/schedules")
    assert bridge_list.status_code == 200
    assert any(s["id"] == sched_id for s in bridge_list.json())

    bridge_execs = bridge_client.get(f"/api/v1/schedules/{sched_id}/executions")
    assert bridge_execs.status_code == 200
    assert len(bridge_execs.json()["executions"]) >= 1

    # 6. Delete schedule via DELETE
    del_resp = client.delete(f"/api/schedules/{sched_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # Verify deleted
    post_del_list = client.get("/api/schedules").json()
    assert not any(s["id"] == sched_id for s in post_del_list)

    # 7. Create on Bridge and Delete via POST alias
    br_create = bridge_client.post("/api/v1/schedules", json={
        "name": "Bridge Scheduled Audit",
        "cron_expression": "*/15 * * * *",
        "prompt": "Bridge audit task"
    })
    assert br_create.status_code == 200
    br_sched_id = br_create.json()["id"]

    br_del_post = bridge_client.post(f"/api/v1/schedules/{br_sched_id}/delete")
    assert br_del_post.status_code == 200
    assert br_del_post.json()["status"] == "success"

def test_chat_api_endpoint():
    response = client.post("/api/chat", json={"prompt": "Perform sanity health check"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "reply" in data
    assert "thinking" in data

def test_chat_api_endpoint_thinking_toggle():
    from unittest.mock import MagicMock
    from krokbot.dashboard.server import set_agent_instance
    mock_agent = MagicMock()
    mock_agent.run_task.return_value = {
        "status": "success",
        "report": "Final Answer: Done.",
        "clean_report": "Final Answer: Done.",
        "raw_report": "<think>Thinking...</think>\n\nFinal Answer: Done.",
        "thinking": "Thinking...",
        "show_thinking": False
    }
    set_agent_instance(mock_agent)
    
    resp = client.post("/api/chat", json={"prompt": "Test prompt", "show_thinking": False})
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["show_thinking"] is False
    assert res_data["thinking"] == "Thinking..."
    assert res_data["reply"] == "Final Answer: Done."
    mock_agent.run_task.assert_called_with("Test prompt", save_mode=None, show_thinking=False)
    
    set_agent_instance(None)

def test_export_health_report(tmp_path):
    report_file = tmp_path / "test_report.md"
    metrics = {"cpu_percent": 20.0, "memory_percent": 50.0, "os_info": "Windows 11"}
    report_content = "All systems operating normally."
    export_health_report(str(report_file), report_content, metrics)
    
    assert os.path.exists(report_file)
    content = report_file.read_text()
    assert "# KrokBot Workstation Health Report" in content
    assert "Windows 11" in content

def test_container_resource_metrics_endpoint():
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "container" in data
    
    c = data["container"]
    assert "cpu_percent" in c
    assert "memory_used_mb" in c
    assert "memory_used_gb" in c
    assert "memory_percent" in c
    assert "storage_service_mb" in c
    assert "storage_service_gb" in c
    assert "storage_models_mb" in c
    assert "storage_data_mb" in c
    assert "disk_percent" in c
    assert "process_count" in c
    assert "is_docker" in c
    assert c["process_count"] >= 1

