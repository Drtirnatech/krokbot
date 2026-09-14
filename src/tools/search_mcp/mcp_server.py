# src/tools/search_mcp/mcp_server.py
import os
import urllib.parse
import httpx
from typing import Optional, List, Dict, Any
from src.tools.search_mcp.crawler_service import CrawlerService
from src.tools.search_mcp.watchdog import WatchdogState

try:
    from fastmcp import FastMCP
    mcp = FastMCP("KrokBot-Local-Search")
except ImportError:
    class DummyFastMCP:
        def __init__(self, name: str):
            self.name = name
        def tool(self):
            def decorator(f):
                return f
            return decorator
        def run(self, **kwargs):
            pass
    mcp = DummyFastMCP("KrokBot-Local-Search")

watchdog = WatchdogState()
crawler = CrawlerService()

SEARXNG_URL = os.getenv("SEARXNG_INTERNAL_URL", "http://127.0.0.1:5160")

async def execute_local_search(
    query: str,
    max_results: int = 3,
    extract_content: bool = True
) -> str:
    watchdog.touch()
    encoded_q = urllib.parse.quote_plus(query)
    search_url = f"{SEARXNG_URL}/search?q={encoded_q}&format=json"

    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(search_url)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])[:max_results]
    except Exception as e:
        return f"### Local Web Search Error\nFailed to query internal SearXNG engine: `{str(e)}`"

    if not results:
        return f"### Local Web Search Results\nNo search results found for query: `{query}`"

    urls_to_crawl = [r["url"] for r in results if r.get("url")]
    page_contents: Dict[str, str] = {}
    if extract_content and urls_to_crawl:
        page_contents = await crawler.extract_batch(urls_to_crawl)

    md_lines = [f"### Local Web Search: `{query}`\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", f"Result #{i}")
        url = r.get("url", "")
        snippet = r.get("content", "").strip()
        md_lines.append(f"#### {i}. [{title}]({url})")
        if snippet:
            md_lines.append(f"**Snippet:** {snippet}\n")
        
        extracted = page_contents.get(url)
        if extracted:
            md_lines.append(f"**Extracted Content:**\n```markdown\n{extracted}\n```\n")
        md_lines.append("---\n")

    return "\n".join(md_lines)

@mcp.tool()
async def local_web_search(
    query: str,
    max_results: int = 3,
    extract_content: bool = True
) -> str:
    """
    Performs a local internet search via SearXNG and retrieves page contents via Crawl4AI.
    Returns cleaned Markdown formatted for LLM ingestion.
    """
    return await execute_local_search(query, max_results, extract_content)

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=5165)
