import pytest
from fastapi.testclient import TestClient
from krokbot.bridge.main import app

client = TestClient(app)

def test_system_summary_endpoint():
    response = client.get("/api/v1/system/summary")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "os_info" in data

def test_storage_endpoint():
    response = client.get("/api/v1/system/storage")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "mount_point" in data[0]

def test_services_endpoint():
    response = client.get("/api/v1/services/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
