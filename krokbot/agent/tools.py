import httpx
from krokbot.sandbox.executor import SandboxExecutor
from typing import Dict, Any

class ToolRegistry:
    def __init__(self, bridge_url: str = "http://localhost:8990"):
        self.bridge_url = bridge_url
        self.sandbox = SandboxExecutor()

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
