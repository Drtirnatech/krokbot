# tests/test_search_mcp_scaffold.py
import os
import yaml
from pathlib import Path

def test_searxng_settings_configuration():
    settings_path = Path("docker/search-mcp/searxng/settings.yml")
    assert settings_path.exists(), "settings.yml must exist"
    with open(settings_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert "search" in cfg
    assert "json" in cfg["search"].get("formats", [])
    assert cfg.get("server", {}).get("port") == 5160
    assert cfg.get("server", {}).get("bind_address") in ("127.0.0.1", "0.0.0.0")

def test_dockerfile_and_supervisor_exist():
    assert Path("docker/search-mcp/Dockerfile").exists()
    assert Path("docker/search-mcp/supervisord.conf").exists()
    assert Path("docker/search-mcp/requirements.txt").exists()
