# tests/test_mcp_server.py
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from src.tools.search_mcp.mcp_server import execute_local_search

def test_execute_local_search_success():
    fake_searxng_response = {
        "results": [
            {"title": "Result 1", "url": "https://example.com/1", "content": "Snippet 1"},
            {"title": "Result 2", "url": "https://example.com/2", "content": "Snippet 2"}
        ]
    }
    
    with patch("httpx.AsyncClient.get") as mock_get, \
         patch("src.tools.search_mcp.crawler_service.CrawlerService.extract_batch", new_callable=AsyncMock) as mock_extract:
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_searxng_response
        mock_get.return_value = mock_resp
        
        mock_extract.return_value = {
            "https://example.com/1": "Page 1 Full Markdown Content",
            "https://example.com/2": "Page 2 Full Markdown Content"
        }
        
        markdown = asyncio.run(execute_local_search(query="python mcp", max_results=2, extract_content=True))
        assert "Result 1" in markdown
        assert "https://example.com/1" in markdown
        assert "Page 1 Full Markdown Content" in markdown
        assert "Snippet 2" in markdown
