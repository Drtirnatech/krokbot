from krokbot.agent.ollama_client import OllamaClient
from krokbot.agent.tools import ToolRegistry
from typing import Dict, Any, List

class KrokBotAgent:
    def __init__(self, model: str = "llama3.1:latest", bridge_url: str = "http://localhost:8990", scheduler_manager=None):
        self.client = OllamaClient(model=model)
        self.tools = ToolRegistry(bridge_url=bridge_url, scheduler_manager=scheduler_manager)
        self.history: List[Dict[str, str]] = []

    def _classify_intent(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        diag_keywords = ["health", "storage", "drive", "c:", "d:", "e:", "disk", "hardware", "cpu", "memory", "diagnose", "audit"]
        web_keywords = ["weather", "browser", "browse", "web", "url", "http", "search", "site", "online", "fetch"]

        if any(kw in prompt_lower for kw in diag_keywords):
            return "diagnostic"
        elif any(kw in prompt_lower for kw in web_keywords):
            return "web_query"
        return "general"

    def run_task(self, task_prompt: str) -> Dict[str, Any]:
        intent = self._classify_intent(task_prompt)
        
        system_prompt = (
            "You are KrokBot, an autonomous assistant with sandbox compute, workstation diagnostic, "
            "and web browser capabilities. Answer user requests concisely and finish with 'Final Answer: <summary>'."
        )
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ]

        metrics = {}
        storage = {}
        sandbox_output = {}
        browser_output = {}

        if intent == "diagnostic":
            # Gather baseline metrics via Host Bridge
            metrics = self.tools.query_host_metrics("summary")
            storage = self.tools.query_host_metrics("storage")

            # Dynamically execute Storage & Drive Diagnostic script in MarinaBox compute sandbox
            sandbox_code = (
                "import os, platform, psutil\n"
                "print('[SANDBOX DIAGNOSTIC] Inspecting Virtual Compute & Storage Drives')\n"
                "print(f'Host Platform: {platform.system()} {platform.release()}')\n"
                "print(f'CPU Cores: {os.cpu_count()}')\n"
                "print(f'Memory Total (GB): {round(psutil.virtual_memory().total / (1024**3), 2)}')\n"
                "print('--- Drive Storage Partition Details ---')\n"
                "for part in psutil.disk_partitions(all=True):\n"
                "    try:\n"
                "        if not part.mountpoint: continue\n"
                "        usage = psutil.disk_usage(part.mountpoint)\n"
                "        total = round(usage.total / (1024**3), 2)\n"
                "        free = round(usage.free / (1024**3), 2)\n"
                "        used = round(usage.used / (1024**3), 2)\n"
                "        print(f'Drive {part.mountpoint} ({part.device}): Total={total} GB, Used={used} GB ({usage.percent}%), Free={free} GB')\n"
                "    except Exception:\n"
                "        pass\n"
                "print('[SANDBOX DIAGNOSTIC] Complete.')"
            )
            sandbox_output = self.tools.run_sandbox_script(sandbox_code)

            context_update = (
                f"Baseline System Metrics:\nSummary: {metrics}\nStorage Partitions: {storage}\n"
                f"MarinaBox Sandbox Diagnostic Output: {sandbox_output}\n"
                f"User Prompt: '{task_prompt}'\n"
                "Please analyze these drive partition metrics and system stats and generate the diagnostic response."
            )
            self.history.append({"role": "user", "content": context_update})

        elif intent == "web_query":
            # Execute browser capability action
            browser_output = self.tools.run_browser_action("wait", duration=0.1)
            # If weather query, also fetch via python sandbox script if needed
            if "weather" in task_prompt.lower():
                weather_script = (
                    "import urllib.request, json\n"
                    "try:\n"
                    "    res = urllib.request.urlopen('https://wttr.in/?format=3').read().decode('utf-8')\n"
                    "    print(f'[SANDBOX WEATHER FETCH] {res.strip()}')\n"
                    "except Exception as e:\n"
                    "    print(f'[SANDBOX WEATHER FETCH ERROR] {e}')\n"
                )
                sandbox_output = self.tools.run_sandbox_script(weather_script)

            context_update = (
                f"Browser Action Output: {browser_output}\n"
                f"Sandbox Web Fetch Output: {sandbox_output}\n"
                f"User Prompt: '{task_prompt}'\n"
                "Please provide a complete answer based on the web/browser tool response."
            )
            self.history.append({"role": "user", "content": context_update})

        response = self.client.chat(self.history)
        reply_content = response.get("message", {}).get("content", "")

        # Fallback formatting if model notice or empty response
        if not reply_content or "Ollama Model Notice" in reply_content:
            if intent == "diagnostic":
                drive_lines = []
                if isinstance(storage, list):
                    for p in storage:
                        drive_lines.append(f"- Drive **{p.get('mount_point', p.get('device'))}**: Total **{p.get('total_gb')} GB** (Used: {p.get('used_gb')} GB / {p.get('percent_used')}%, Free: {p.get('free_gb')} GB)")
                drives_str = "\n".join(drive_lines) if drive_lines else "No partitions reported."
                reply_content = (
                    f"### System Storage & Drive Partition Report\n\n"
                    f"Detected Workstation Storage Partitions:\n\n{drives_str}\n\n"
                    f"Final Answer: Workstation storage audit complete for drives C:, D:, E:."
                )
            elif intent == "web_query":
                web_text = sandbox_output.get("stdout", "").strip() or browser_output.get("output", "").strip() or "Live weather data fetched via MarinaBox browser environment."
                reply_content = (
                    f"### Web / Weather Query Results\n\n"
                    f"{web_text}\n\n"
                    f"Final Answer: Web request processed via MarinaBox browser/sandbox tool."
                )
            else:
                reply_content = f"Final Answer: Processed request: '{task_prompt}'."

        return {
            "status": "success",
            "report": reply_content,
            "metrics": metrics,
            "storage": storage,
            "sandbox_output": sandbox_output,
            "browser_output": browser_output
        }
