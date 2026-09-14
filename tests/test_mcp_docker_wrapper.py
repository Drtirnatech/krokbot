# tests/test_mcp_docker_wrapper.py
import pytest
from unittest.mock import patch, MagicMock
from client.mcp_docker_wrapper import McpDockerClientWrapper

def test_wrapper_ensures_container_running():
    wrapper = McpDockerClientWrapper(container_name="test-search-mcp")
    with patch("subprocess.run") as mock_run, \
         patch.object(wrapper, "_is_server_healthy", side_effect=[False, True]):
        
        # Simulate container stopped
        mock_inspect = MagicMock()
        mock_inspect.returncode = 0
        mock_inspect.stdout = "false\n" # not running
        
        mock_start = MagicMock()
        mock_start.returncode = 0

        mock_run.side_effect = [mock_inspect, mock_start]

        ready = wrapper.ensure_container_running(timeout=2.0)
        assert ready is True
        assert mock_run.call_count == 2

def test_wrapper_search_fallback_when_unavailable():
    wrapper = McpDockerClientWrapper(container_name="test-search-mcp")
    with patch.object(wrapper, "ensure_container_running", return_value=False):
        res = wrapper.search(query="test")
        assert res.get("status") == "error"
        assert "CONTAINER_UNAVAILABLE" in res.get("error", "")

def test_wrapper_search_success():
    wrapper = McpDockerClientWrapper(container_name="test-search-mcp")
    with patch.object(wrapper, "ensure_container_running", return_value=True), \
         patch("httpx.Client.post") as mock_post:
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "### Markdown Search Results"
        mock_post.return_value = mock_resp
        
        res = wrapper.search(query="test")
        assert res.get("status") == "success"
        assert res.get("markdown") == "### Markdown Search Results"
