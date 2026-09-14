# src/tools/search_mcp/crawler_service.py
import re
import asyncio
import httpx
from typing import List, Dict, Any, Optional

class CrawlerService:
    """
    Extracts web content using Fast-HTTP first, falling back to Crawl4AI Playwright.
    Enforces scoped browser lifecycle to keep memory footprint under 500 MB.
    """
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def _html_to_markdown(self, html: str) -> str:
        text = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<noscript.*?>.*?</noscript>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Convert simple headers and paragraphs
        text = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n## \1\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'\n* \1', text, flags=re.IGNORECASE)
        # Strip remaining tags
        text = re.sub(r'<[^>]+>', ' ', text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = '\n\n'.join(lines)
        return cleaned[:4000]

    async def extract_url(self, url: str) -> str:
        # 1. Fast-HTTP extraction attempt
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and resp.text:
                    content = self._html_to_markdown(resp.text)
                    if content and len(content.strip()) > 10:
                        return content
        except Exception:
            pass

        # 2. Scoped Playwright / Crawl4AI fallback
        try:
            from crawl4ai import AsyncWebCrawler
            async with AsyncWebCrawler(verbose=False) as crawler:
                res = await crawler.arun(url=url)
                if res and getattr(res, "markdown", None):
                    return res.markdown[:4000]
        except Exception as e:
            return f"*(Content extraction failed: {str(e)})*"

        return "*(Empty response from target)*"

    async def extract_batch(self, urls: List[str]) -> Dict[str, str]:
        tasks = [self.extract_url(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        extracted = {}
        for url, res in zip(urls, results):
            if isinstance(res, Exception):
                extracted[url] = f"*(Extraction error: {str(res)})*"
            else:
                extracted[url] = res
        return extracted
