import pytest

@pytest.fixture
def mock_host_metrics():
    return {
        "cpu_percent": 15.5,
        "memory_percent": 45.2,
        "disk_percent": 68.0,
        "os_info": "Windows 11"
    }
