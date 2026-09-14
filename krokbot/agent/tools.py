import os
import httpx
import asyncio
from krokbot.sandbox.executor import SandboxExecutor
from krokbot.sandbox.browser import BrowserToolWrapper
from krokbot.config.tools_config import get_tools_manager, AgentToolsManager
from typing import Dict, Any, Optional

def discover_host_bridge_url(explicit_url: Optional[str] = None) -> str:
    """Intelligently discover the live Host Bridge URL across native and container environments."""
    if explicit_url:
        return explicit_url.rstrip("/")

    env_url = os.getenv("BRIDGE_URL")
    if env_url:
        return env_url.rstrip("/")

    is_container = os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER")
    candidates = []
    
    if is_container:
        candidates.extend([
            "http://host.docker.internal:8992",
            "http://host.docker.internal:8990",
        ])
        # Container default gateway in /proc/net/route
        try:
            if os.path.exists("/proc/net/route"):
                with open("/proc/net/route", "r") as f:
                    for line in f.readlines()[1:]:
                        fields = line.strip().split()
                        if len(fields) >= 3 and fields[1] == "00000000":
                            gw_hex = fields[2]
                            gw_ip = f"{int(gw_hex[6:8], 16)}.{int(gw_hex[4:6], 16)}.{int(gw_hex[2:4], 16)}.{int(gw_hex[0:2], 16)}"
                            candidates.append(f"http://{gw_ip}:8992")
                            candidates.append(f"http://{gw_ip}:8990")
        except Exception:
            pass

        # DNS nameserver from /etc/resolv.conf
        try:
            if os.path.exists("/etc/resolv.conf"):
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if "ExtServers:" in line and "host(" in line:
                            part = line.split("host(")[1].split(")")[0].strip()
                            candidates.append(f"http://{part}:8992")
                            candidates.append(f"http://{part}:8990")
        except Exception:
            pass

    # Native host candidates
    candidates.extend([
        "http://127.0.0.1:8992",
        "http://localhost:8992",
        "http://127.0.0.1:8990",
        "http://localhost:8990"
    ])

    import socket
    from urllib.parse import urlparse
    for cand in candidates:
        try:
            parsed = urlparse(cand)
            host = parsed.hostname
            port = parsed.port or 80
            s = socket.create_connection((host, port), timeout=0.2)
            s.close()
            return cand
        except Exception:
            continue

    return "http://host.docker.internal:8992" if is_container else "http://localhost:8992"

class ToolRegistry:
    def __init__(self, bridge_url: Optional[str] = None, scheduler_manager=None, tools_manager: Optional[AgentToolsManager] = None):
        self.configured_bridge_url = bridge_url
        self._discovered_bridge_url = None
        self.bridge_url = bridge_url or os.getenv("BRIDGE_URL", "http://localhost:8990")
        self.sandbox = SandboxExecutor()
        self.browser = BrowserToolWrapper()
        self.scheduler_manager = scheduler_manager
        self.tools_manager = tools_manager or get_tools_manager()

    def get_bridge_url(self) -> str:
        if not self._discovered_bridge_url:
            self._discovered_bridge_url = discover_host_bridge_url(self.configured_bridge_url)
            self.bridge_url = self._discovered_bridge_url
        return self._discovered_bridge_url

    def is_tool_enabled(self, tool_id: str) -> bool:
        if self.tools_manager:
            return self.tools_manager.is_tool_enabled(tool_id)
        return True

    def search_local_mcp(self, query: str, max_results: int = 3, extract_content: bool = True) -> Dict[str, Any]:
        if not self.is_tool_enabled("local_search_mcp"):
            return {
                "status": "blocked",
                "error": "SECURITY_POLICY_VIOLATION",
                "message": "[SECURITY GOVERNANCE ERROR] 'Local Search MCP' tool is disabled by administrator policy in agent_tools.json. Local web search is blocked.",
                "markdown": "*(Local Search MCP disabled by administrator policy)*"
            }
        from client.mcp_docker_wrapper import McpDockerClientWrapper
        wrapper = McpDockerClientWrapper()
        return wrapper.search(query=query, max_results=max_results, extract_content=extract_content)

    def query_host_metrics(self, endpoint_type: str = "summary") -> Dict[str, Any]:
        if not self.is_tool_enabled("os_bridge"):
            return {
                "error": "SECURITY_POLICY_VIOLATION",
                "message": "[SECURITY GOVERNANCE ERROR] 'OS Bridge (Host Hardware)' tool is disabled by administrator policy in agent_tools.json. Access to host hardware metrics is blocked."
            }
        bridge_url = self.get_bridge_url()
        url = f"{bridge_url}/api/v1/system/{endpoint_type}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                return resp.json()
        except Exception as e:
            return {"error": f"Failed to connect to Host Bridge ({bridge_url}): {str(e)}"}

    def run_sandbox_script(self, code: str) -> Dict[str, Any]:
        if not self.is_tool_enabled("python_scripting"):
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": "[SECURITY GOVERNANCE ERROR] 'Python Scripting' tool is disabled by administrator policy in agent_tools.json. Python code execution is blocked."
            }
        if not self.is_tool_enabled("sandbox_cli"):
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": "[SECURITY GOVERNANCE ERROR] 'Sandbox CLI' tool is disabled by administrator policy in agent_tools.json. Container execution is blocked."
            }
        return self.sandbox.execute_script(code, language="python")

    def run_sandbox_file(self, filename: str) -> Dict[str, Any]:
        if not self.is_tool_enabled("python_scripting"):
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": f"[SECURITY GOVERNANCE ERROR] 'Python Scripting' tool is disabled by administrator policy in agent_tools.json. Execution of '{filename}' is blocked."
            }
        if not self.is_tool_enabled("sandbox_cli"):
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": f"[SECURITY GOVERNANCE ERROR] 'Sandbox CLI' tool is disabled by administrator policy in agent_tools.json. Execution of '{filename}' is blocked."
            }
        return self.sandbox.execute_file(filename)

    def run_browser_action(
        self,
        action: str,
        text: Optional[str] = None,
        coordinate: Optional[tuple] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not self.is_tool_enabled("browser_function"):
            return {
                "status": "error",
                "output": "[SECURITY GOVERNANCE ERROR] 'Browser Function' tool is disabled by administrator policy in agent_tools.json. Web queries and browser actions are blocked.",
                "base64_image": None
            }
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

    def run_system_cli(self, command: str) -> Dict[str, Any]:
        """Execute command directly on the host operating system CLI."""
        if not self.is_tool_enabled("system_cli"):
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": "[SECURITY GOVERNANCE ERROR] 'System CLI Functions (Host OS)' tool is disabled by administrator policy in agent_tools.json. Execution on host system CLI is blocked."
            }
        bridge_url = self.get_bridge_url()
        url = f"{bridge_url}/api/v1/system/cli"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json={"command": command})
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 403:
                    data = resp.json()
                    return {
                        "exit_code": 126,
                        "stdout": "",
                        "stderr": data.get("detail", "Access to Host CLI denied by security policy.")
                    }
                else:
                    return {
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": f"Host Bridge returned HTTP {resp.status_code}: {resp.text}"
                    }
        except httpx.ConnectError:
            # Clear cached URL and re-probe in case bridge just started or changed IP
            self._discovered_bridge_url = None
            retry_url = self.get_bridge_url()
            if retry_url != bridge_url:
                try:
                    with httpx.Client(timeout=30.0) as client:
                        resp = client.post(f"{retry_url}/api/v1/system/cli", json={"command": command})
                        if resp.status_code == 200:
                            return resp.json()
                except Exception:
                    pass

            is_docker = os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER")
            instructions = (
                f"Could not connect to KrokBot Host Bridge at {bridge_url}.\n\n"
                f"The agent is running inside an isolated Docker container and needs the Host Bridge running on your host system.\n"
                f"To enable Host OS CLI execution:\n"
                f"  1. On your host machine, launch the Host Bridge:\n"
                f"       - Windows: powershell -File .\\run_host_bridge.ps1 (or python run_host_bridge.py)\n"
                f"       - Linux/macOS: ./run_host_bridge.sh (or python3 run_host_bridge.py)\n"
                f"  2. Verify 'System CLI Functions (Host OS)' is enabled in the Tool Policy Manager tab.\n"
            ) if is_docker else (
                f"Could not connect to KrokBot Host Bridge at {bridge_url}. Ensure the bridge service is running (python run_host_bridge.py)."
            )
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": instructions
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Failed to execute system CLI via Host Bridge ({bridge_url}): {str(e)}"
            }

    def schedule_cron_task(self, name: str, cron_expression: str, prompt: str, target_script: Optional[str] = None) -> Dict[str, Any]:
        if self.scheduler_manager:
            job_func = None
            if target_script:
                def script_runner(task_prompt=None, schedule_id=None):
                    if not self.is_tool_enabled("python_scripting") or not self.is_tool_enabled("sandbox_cli"):
                        msg = "[SECURITY GOVERNANCE ERROR] Scheduled cron task execution blocked: 'Python Scripting' tool is disabled by administrator policy."
                        print(f"[CRON JOB BLOCKED] {msg}")
                        return {"exit_code": 126, "stdout": "", "stderr": msg}
                    res = self.sandbox.execute_file(target_script)
                    print(f"[CRON JOB EXECUTION] Script: {target_script} | Exit Code: {res.get('exit_code')}")
                    if res.get("stdout"):
                        print(f"[CRON STDOUT]:\n{res['stdout'].strip()}")
                    return res
                job_func = script_runner

            item = self.scheduler_manager.add_schedule(name, cron_expression, prompt, target_script=target_script, job_func=job_func)
            return {"status": "success", "schedule": item}
        return {"status": "error", "message": "Scheduler manager not initialized"}



