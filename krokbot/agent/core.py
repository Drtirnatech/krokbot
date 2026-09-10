from krokbot.agent.ollama_client import OllamaClient
from krokbot.agent.tools import ToolRegistry
from typing import Dict, Any, List

class KrokBotAgent:
    def __init__(self, model: str = "llama3.2", bridge_url: str = "http://localhost:8990", scheduler_manager=None):
        self.client = OllamaClient(model=model)
        self.tools = ToolRegistry(bridge_url=bridge_url, scheduler_manager=scheduler_manager)
        self.history: List[Dict[str, str]] = []

    def run_task(self, task_prompt: str) -> Dict[str, Any]:
        system_prompt = (
            "You are KrokBot, an autonomous workstation health and troubleshooting agent. "
            "Inspect system metrics, develop python diagnostic scripts in your sandbox if needed, "
            "and produce a clear health report ending with 'Final Answer: <summary>'."
        )
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ]

        # Gather baseline metrics via Host Bridge
        metrics = self.tools.query_host_metrics("summary")
        storage = self.tools.query_host_metrics("storage")

        # Dynamically execute Python diagnostic script in MarinaBox compute sandbox
        sandbox_code = (
            "import os, platform, psutil\n"
            "print('[SANDBOX DIAGNOSTIC] Inspecting Virtual Compute & OS Environment')\n"
            "print(f'Host Platform: {platform.system()} {platform.release()}')\n"
            "print(f'CPU Cores: {os.cpu_count()}')\n"
            "print(f'Memory Total (GB): {round(psutil.virtual_memory().total / (1024**3), 2)}')\n"
            "print('[SANDBOX DIAGNOSTIC] Complete.')"
        )
        sandbox_output = self.tools.run_sandbox_script(sandbox_code)

        context_update = (
            f"Baseline System Metrics:\nSummary: {metrics}\nStorage: {storage}\n"
            f"MarinaBox Sandbox Diagnostic Output: {sandbox_output}\n"
            "Please analyze these metrics and generate the final diagnostic health report."
        )
        self.history.append({"role": "user", "content": context_update})

        response = self.client.chat(self.history)
        reply_content = response.get("message", {}).get("content", "No output generated.")

        return {
            "status": "success",
            "report": reply_content,
            "metrics": metrics,
            "storage": storage,
            "sandbox_output": sandbox_output
        }
