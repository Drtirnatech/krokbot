import os
import pytest
from fastapi.testclient import TestClient
from krokbot.dashboard.server import app
from krokbot.sysops.diagnostics import get_edge_diagnostics
from krokbot.sysops.processes import get_process_manager
from krokbot.sysops.watchdog import get_self_healing_watchdog

client = TestClient(app)

def test_edge_diagnostics():
    diag = get_edge_diagnostics()
    
    # 1. Thermal metrics
    thermals = diag.get_thermal_metrics()
    assert "max_temp_c" in thermals
    assert "status" in thermals
    assert thermals["max_temp_c"] > 0
    assert len(thermals["sensors"]) >= 1

    # 2. Storage metrics
    storage = diag.get_storage_metrics()
    assert len(storage) >= 1
    assert "total_gb" in storage[0]
    assert "used_gb" in storage[0]
    assert "percent" in storage[0]

    # 3. Top processes
    procs = diag.get_top_processes(limit=5)
    assert len(procs) >= 1
    assert "pid" in procs[0]
    assert "memory_rss_mb" in procs[0]

    # 4. Network metrics
    net = diag.get_network_metrics()
    assert "bytes_sent_mb" in net
    assert "bytes_recv_mb" in net

    # 5. Full diagnostic bundle
    full = diag.get_full_diagnostics()
    assert "cpu" in full
    assert "thermals" in full
    assert "storage" in full

def test_process_manager_safety_guards():
    pm = get_process_manager()
    current_pid = os.getpid()

    # Safety checks
    assert pm.is_pid_protected(1) is True
    assert pm.is_pid_protected(current_pid) is True

    # Attempting to terminate PID 1 or self must raise PermissionError
    with pytest.raises(PermissionError):
        pm.terminate_process(1)

    with pytest.raises(PermissionError):
        pm.terminate_process(current_pid)

    # Attempting to terminate nonexistent PID raises LookupError
    with pytest.raises(LookupError):
        pm.terminate_process(99999999)

    # Process listing
    p_list = pm.list_processes(limit=10)
    assert len(p_list) >= 1
    assert all("is_protected" in p for p in p_list)

def test_process_manager_system_cleanup():
    pm = get_process_manager()
    res = pm.run_system_cleanup()
    assert res["status"] == "success"
    assert "gc_objects_collected" in res
    assert "memory_recovered_mb" in res

def test_self_healing_watchdog():
    watchdog = get_self_healing_watchdog()
    
    # List policies
    policies = watchdog.list_policies()
    assert len(policies) >= 3
    
    # Toggle policy
    p_id = "policy_storage_pressure"
    prev_state = next(p["enabled"] for p in policies if p["id"] == p_id)
    toggled = watchdog.toggle_policy(p_id)
    assert toggled["enabled"] == (not prev_state)
    # Restore
    watchdog.toggle_policy(p_id)

    # Evaluate health
    remediations = watchdog.evaluate_health()
    assert isinstance(remediations, list)

def test_sysops_api_endpoints():
    # 1. GET /api/sysops/telemetry
    res = client.get("/api/sysops/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "diagnostics" in data
    assert "thermals" in data["diagnostics"]

    # 2. GET /api/sysops/processes
    res = client.get("/api/sysops/processes")
    assert res.status_code == 200
    assert "processes" in res.json()
    assert len(res.json()["processes"]) >= 1

    # 3. POST /api/sysops/processes/1/kill (Must be 403 Forbidden)
    res = client.post("/api/sysops/processes/1/kill")
    assert res.status_code == 403

    # 4. POST /api/sysops/cleanup
    res = client.post("/api/sysops/cleanup")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 5. GET /api/sysops/watchdog/policies
    res = client.get("/api/sysops/watchdog/policies")
    assert res.status_code == 200
    assert "policies" in res.json()
