import httpx
import asyncio
from krokbot.sandbox.executor import SandboxExecutor
from krokbot.sandbox.browser import BrowserToolWrapper
from typing import Dict, Any, Optional

class ToolRegistry:
    def __init__(self, bridge_url: str = "http://localhost:8990", scheduler_manager=None):
        self.bridge_url = bridge_url
        self.sandbox = SandboxExecutor()
        self.browser = BrowserToolWrapper()
        self.scheduler_manager = scheduler_manager

    def query_host_metrics(self, endpoint_type: str = "summary") -> Dict[str, Any]:
        url = f"{self.bridge_url}/api/v1/system/{endpoint_type}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                return resp.json()
        except Exception as e:
            return {"error": f"Failed to connect to Host Bridge: {str(e)}"}

    def run_sandbox_script(self, code: str) -> Dict[str, Any]:
        return self.sandbox.execute_script(code, language="python")

    def run_browser_action(
        self,
        action: str,
        text: Optional[str] = None,
        coordinate: Optional[tuple] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(
                    self.browser.execute_action(action, text=text, coordinate=coordinate, **kwargs)
                )
            return asyncio.run(
                self.browser.execute_action(action, text=text, coordinate=coordinate, **kwargs)
            )
        except Exception as e:
            return {"status": "error", "output": f"Browser tool error: {str(e)}", "base64_image": None}

    def schedule_cron_task(self, name: str, cron_expression: str, prompt: str) -> Dict[str, Any]:
        if self.scheduler_manager:
            item = self.scheduler_manager.add_schedule(name, cron_expression, prompt)
            return {"status": "success", "schedule": item}
        return {"status": "error", "message": "Scheduler manager not initialized"}

