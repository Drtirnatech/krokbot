# client/mcp_docker_wrapper.py
import subprocess
import time
import socket
import httpx
from typing import Dict, Any, Optional

class McpDockerClientWrapper:
    """
    Client-side wrapper that manages on-demand lazy starting of the krokbot-search-mcp
    container, relays MCP requests, and handles offline fallbacks.
    """
    def __init__(
        self,
        container_name: str = "krokbot-search-mcp",
        server_url: str = "http://127.0.0.1:5165"
    ):
        self.container_name = container_name
        self.server_url = server_url.rstrip("/")

    def _is_server_healthy(self) -> bool:
        try:
            # Check TCP port reachability
            s = socket.create_connection(("127.0.0.1", 5165), timeout=0.3)
            s.close()
            return True
        except Exception:
            return False

    def is_container_running(self) -> bool:
        try:
            res = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.container_name],
                capture_output=True, text=True, timeout=3
            )
            return res.returncode == 0 and res.stdout.strip().lower() == "true"
        except Exception:
            return False

    def ensure_container_running(self, timeout: float = 12.0) -> bool:
        if self._is_server_healthy():
            return True

        # Check if container is running or stopped
        if not self.is_container_running():
            print(f"[SearchMCP-Client] Starting container '{self.container_name}' on demand...")
            start_res = subprocess.run(
                ["docker", "start", self.container_name],
                capture_output=True, text=True, timeout=8
            )
            if start_res.returncode != 0:
                # If start failed, check if we need to run it from image
                run_res = subprocess.run(
                    ["docker", "run", "-d", "--name", self.container_name, "-p", "5165:5165", self.container_name],
                    capture_output=True, text=True, timeout=8
                )
                if run_res.returncode != 0:
                    print(f"[SearchMCP-Client] Notice: container '{self.container_name}' could not be started: {start_res.stderr.strip()}")
                    return False

        # Wait for HTTP server readiness
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._is_server_healthy():
                return True
            time.sleep(0.4)

        return False

    def search(
        self,
        query: str,
        max_results: int = 3,
        extract_content: bool = True,
        timeout: float = 25.0
    ) -> Dict[str, Any]:
        if not self.ensure_container_running():
            return {
                "status": "error",
                "error": "CONTAINER_UNAVAILABLE",
                "markdown": f"*(Local search container '{self.container_name}' is not running or could not be reached on port 5165)*"
            }

        payload = {
            "query": query,
            "max_results": max_results,
            "extract_content": extract_content
        }

        # Issue call via FastMCP tool call or direct endpoint
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(f"{self.server_url}/tools/local_web_search", json=payload)
                if resp.status_code == 200:
                    return {"status": "success", "markdown": resp.text}
                return {"status": "error", "error": resp.text, "markdown": f"*(Search error {resp.status_code})*"}
        except Exception as e:
            return {"status": "error", "error": str(e), "markdown": f"*(Search request error: {str(e)})*"}
