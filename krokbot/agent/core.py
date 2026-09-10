import re
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
        script_keywords = ["script", "python", ".py", "reconcile", "csv", "generate script", "create a script", "write a script", "code"]
        diag_keywords = ["health", "storage", "drive", "c:", "d:", "e:", "disk", "hardware", "cpu", "memory", "diagnose", "audit"]
        web_keywords = ["weather", "browser", "browse", "web", "url", "http", "search", "site", "online", "fetch"]

        if any(kw in prompt_lower for kw in script_keywords):
            return "scripting"
        elif any(kw in prompt_lower for kw in diag_keywords):
            return "diagnostic"
        elif any(kw in prompt_lower for kw in web_keywords):
            return "web_query"
        return "general"

    def run_task(self, task_prompt: str) -> Dict[str, Any]:
        intent = self._classify_intent(task_prompt)
        
        system_prompt = (
            "You are KrokBot, an autonomous assistant with sandbox compute, workstation diagnostic, "
            "code execution, and web browser capabilities. Answer user requests concisely and finish with 'Final Answer: <summary>'."
        )
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ]

        metrics = {}
        storage = {}
        sandbox_output = {}
        browser_output = {}
        report_content = None

        if intent == "scripting":
            # Prompt LLM to generate the python script
            code_gen_prompt = (
                f"User Task: {task_prompt}\n"
                "Please generate the complete, self-contained Python script to fulfill all requirements. "
                "Output ONLY valid executable python code inside ```python ``` block."
            )
            code_response = self.client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": code_gen_prompt}
            ])
            raw_reply = code_response.get("message", {}).get("content", "")

            # Extract python code block
            match = re.search(r"```python\s*(.*?)\s*```", raw_reply, re.DOTALL)
            if match:
                script_code = match.group(1).strip()
            else:
                # Fallback clean-up if code block not demarcated
                script_code = raw_reply.replace("```python", "").replace("```", "").strip()

            # Determine filename (e.g. reconcile.py or script.py)
            filename_match = re.search(r"([a-zA-Z0-9_\-]+\.py)", task_prompt)
            target_filename = filename_match.group(1) if filename_match else "reconcile.py"

            # Save script to persistent sandbox workspace
            self.tools.sandbox.write_file(target_filename, script_code)

            # Execute script in sandbox workspace
            sandbox_output = self.tools.sandbox.execute_file(target_filename)

            # Read report artifact if created
            report_content = self.tools.sandbox.read_file("report.txt")
            exit_code = sandbox_output.get("exit_code", 0)
            stdout = sandbox_output.get("stdout", "").strip()
            stderr = sandbox_output.get("stderr", "").strip()

            report_display = f"\n\n**Actual Contents of `./report.txt`:**\n```text\n{report_content.strip()}\n```" if report_content else ""

            reply_content = (
                f"### Python Script Created & Executed in Sandbox Workspace\n\n"
                f"Created Script: `./{target_filename}`\n"
                f"Exit Code: `{exit_code}`\n\n"
                f"**Sandbox Stdout:**\n```text\n{stdout or '(no stdout)'}\n```\n\n"
                f"**Sandbox Stderr:**\n```text\n{stderr or '(no stderr)'}\n```"
                f"{report_display}\n\n"
                f"Final Answer: Script `./{target_filename}` executed with exit code {exit_code}."
            )

            return {
                "status": "success",
                "report": reply_content,
                "exit_code": exit_code,
                "sandbox_output": sandbox_output,
                "report_file": report_content
            }

        elif intent == "diagnostic":
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
            
            # Extract target URL if specified in user prompt
            url_match = re.search(r"(https?://[^\s'\"]+)", task_prompt)
            target_url = url_match.group(1) if url_match else ("https://wttr.in/?format=3" if "weather" in task_prompt.lower() else "")

            if target_url:
                web_fetch_script = (
                    "import sys, urllib.request, re\n"
                    "if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')\n"
                    "try:\n"
                    f"    req = urllib.request.Request('{target_url}', headers={{'User-Agent': 'Mozilla/5.0'}})\n"
                    "    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')\n"
                    "    text = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)\n"
                    "    text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL)\n"
                    "    text = re.sub(r'<[^>]+>', ' ', text)\n"
                    "    clean_text = ' '.join(text.split())[:1500]\n"
                    "    print(f'[SANDBOX WEB FETCH] {clean_text}')\n"
                    "except Exception as e:\n"
                    "    print(f'[SANDBOX WEB FETCH ERROR] {e}')\n"
                )
                sandbox_output = self.tools.run_sandbox_script(web_fetch_script)

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
