import os
import pytest
from unittest.mock import patch, MagicMock
from krokbot.model_manager import (
    load_config,
    get_available_models,
    ensure_model_available,
    download_model_file,
    download_state,
    delete_model_file
)
from fastapi.testclient import TestClient
from krokbot.dashboard.server import app

client = TestClient(app)

def test_load_config_defaults(tmp_path):
    # Non-existent path returns defaults
    cfg = load_config(str(tmp_path / "missing.yaml"))
    assert "model" in cfg
    assert cfg["model"]["name"] == "Qwen3-4B-Q4_K_M"

def test_load_config_custom(tmp_path):
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text("""
model:
  name: "Custom-Test"
  filename: "custom.gguf"
  context_size: 4096
  auto_download: false
server:
  port: 9000
""", encoding="utf-8")

    cfg = load_config(str(custom_yaml))
    assert cfg["model"]["name"] == "Custom-Test"
    assert cfg["model"]["filename"] == "custom.gguf"
    assert cfg["model"]["context_size"] == 4096
    assert cfg["server"]["port"] == 9000

def test_get_available_models(tmp_path):
    (tmp_path / "model1.gguf").write_bytes(b"dummy model data")
    (tmp_path / "model2.gguf").write_bytes(b"another dummy model data")
    (tmp_path / "ignore.txt").write_text("not a model")

    models = get_available_models(str(tmp_path))
    filenames = [m["filename"] for m in models]
    assert "model1.gguf" in filenames
    assert "model2.gguf" in filenames
    assert "ignore.txt" not in filenames

def test_ensure_model_available_existing(tmp_path):
    target = tmp_path / "test-model.gguf"
    target.write_bytes(b"data")
    
    cfg = {
        "model": {"filename": "test-model.gguf", "auto_download": False}
    }
    with patch("krokbot.model_manager.find_models_dir", return_value=str(tmp_path)):
        found = ensure_model_available(cfg)
        assert found == str(target)

def test_download_model_file_success(tmp_path):
    target = tmp_path / "downloaded.gguf"
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "10"}
    mock_resp.iter_bytes.return_value = [b"12345", b"67890"]

    with patch("httpx.stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value = mock_resp
        success = download_model_file("https://example.com/model.gguf", str(target))
        assert success is True
        assert target.exists()
        assert target.read_bytes() == b"1234567890"
        assert download_state["status"] == "complete"

def test_dashboard_llamacpp_endpoints():
    with patch("krokbot.agent.llamacpp_client.LlamaCppClient.is_alive", return_value=True):
        resp = client.get("/api/llamacpp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert "loaded_models" in data

    resp_models = client.get("/api/models")
    assert resp_models.status_code == 200
    assert "available" in resp_models.json()
    assert "catalog" in resp_models.json()

@patch("krokbot.agent.llamacpp_client.LlamaCppClient.chat")
def test_dashboard_direct_prompt(mock_chat):
    mock_chat.return_value = {"message": {"content": "Direct LLM test response."}}
    resp = client.post("/api/llamacpp/prompt", json={"prompt": "Hello Llama", "temperature": 0.5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["reply"] == "Direct LLM test response."
    assert "latency_ms" in data

def test_delete_model_file(tmp_path):
    target = tmp_path / "to_delete.gguf"
    target.write_bytes(b"model data to purge")
    part_target = tmp_path / "to_delete.gguf.part"
    part_target.write_bytes(b"partial chunk")
    
    assert target.exists()
    assert part_target.exists()
    
    deleted = delete_model_file("to_delete.gguf", models_dir=str(tmp_path))
    assert deleted is True
    assert not target.exists()
    assert not part_target.exists()
    
    # Deleting non-existent file returns False
    assert delete_model_file("missing.gguf", models_dir=str(tmp_path)) is False
    
    # Invalid extension raises ValueError
    with pytest.raises(ValueError):
        delete_model_file("malicious.sh", models_dir=str(tmp_path))

def test_dashboard_delete_model_endpoint(tmp_path):
    target = tmp_path / "api_delete_test.gguf"
    target.write_bytes(b"dummy")
    
    with patch("krokbot.model_manager.find_models_dir", return_value=str(tmp_path)):
        del_resp = client.delete("/api/models/api_delete_test.gguf")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"
        assert not target.exists()
        
        # Subsequent delete returns 404
        del_404 = client.delete("/api/models/api_delete_test.gguf")
        assert del_404.status_code == 404

def test_set_active_model_basic(tmp_path):
    from krokbot.model_manager import set_active_model
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "qwen2.5.gguf").write_bytes(b"qwen weights")
    (models_dir / "llama3.gguf").write_bytes(b"llama weights")
    
    cfg_file = tmp_path / "test_krokbot_config.yaml"
    cfg_file.write_text("""
model:
  name: "Qwen"
  filename: "qwen2.5.gguf"
  context_size: 2048
  chat_format: "chatml"
catalog:
  llama3:
    name: "Llama 3 8B"
    filename: "llama3.gguf"
    context_size: 4096
    chat_format: "llama-3"
""", encoding="utf-8")

    # Set llama3 as active model
    res = set_active_model("llama3.gguf", config_path=str(cfg_file), models_dir=str(models_dir), restart_server=False)
    assert res["status"] == "success"
    assert res["filename"] == "llama3.gguf"
    assert res["name"] == "Llama 3 8B"
    assert res["context_size"] == 4096
    assert res["chat_format"] == "llama-3"

    # Verify persisted in YAML
    updated_cfg = load_config(str(cfg_file))
    assert updated_cfg["model"]["filename"] == "llama3.gguf"
    assert updated_cfg["model"]["name"] == "Llama 3 8B"
    assert updated_cfg["model"]["context_size"] == 4096

    # Test activating non-existent model raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        set_active_model("ghost.gguf", config_path=str(cfg_file), models_dir=str(models_dir), restart_server=False)

    # Test invalid extension raises ValueError
    with pytest.raises(ValueError):
        set_active_model("bad.bin", config_path=str(cfg_file), models_dir=str(models_dir), restart_server=False)

def test_dashboard_activate_model_endpoint(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "phi3.gguf").write_bytes(b"phi weights")
    
    cfg_file = tmp_path / "krokbot_config.yaml"
    cfg_file.write_text("model:\n  filename: other.gguf\n", encoding="utf-8")

    with patch("krokbot.model_manager.find_models_dir", return_value=str(models_dir)), \
         patch("krokbot.model_manager.find_config_file", return_value=str(cfg_file)):
        resp = client.post("/api/models/phi3.gguf/activate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["filename"] == "phi3.gguf"

        # Check 404 on missing model
        resp_404 = client.post("/api/models/missing_model.gguf/activate")
        assert resp_404.status_code == 404

