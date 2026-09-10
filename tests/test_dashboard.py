import pytest
import os
from fastapi.testclient import TestClient
from krokbot.dashboard.server import app, export_health_report

client = TestClient(app)

def test_dashboard_index_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "KrokBot Workstation Dashboard" in response.text

def test_schedules_api_endpoints():
    response = client.get("/api/schedules")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_export_health_report(tmp_path):
    report_file = tmp_path / "test_report.md"
    metrics = {"cpu_percent": 20.0, "memory_percent": 50.0, "os_info": "Windows 11"}
    report_content = "All systems operating normally."
    export_health_report(str(report_file), report_content, metrics)
    
    assert os.path.exists(report_file)
    content = report_file.read_text()
    assert "# KrokBot Workstation Health Report" in content
    assert "Windows 11" in content
