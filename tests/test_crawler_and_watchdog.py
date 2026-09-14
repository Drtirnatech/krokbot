# tests/test_crawler_and_watchdog.py
import pytest
import time
import os
from unittest.mock import patch, AsyncMock
from src.tools.search_mcp.crawler_service import CrawlerService
from src.tools.search_mcp.watchdog import WatchdogState

def test_crawler_service_fast_http():
    import asyncio
    service = CrawlerService()
    html_sample = "<html><body><h1>Test Title</h1><p>This is a paragraph of content.</p></body></html>"
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = html_sample
        mock_get.return_value = mock_resp
        
        result = asyncio.run(service.extract_url("https://example.com"))
        assert "Test Title" in result
        assert "This is a paragraph of content" in result

def test_watchdog_state_touch_and_expiry(tmp_path):
    activity_file = tmp_path / "mcp_activity"
    watchdog = WatchdogState(timeout_seconds=1, activity_file=activity_file)
    watchdog.touch()
    assert not watchdog.is_expired()
    time.sleep(1.1)
    assert watchdog.is_expired()
