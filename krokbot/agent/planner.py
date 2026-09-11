import re
from typing import Dict, Any, List, Optional

class WorkflowPlan:
    def __init__(self, is_sequential: bool, steps: List[Dict[str, Any]], summary: str = ""):
        self.is_sequential = is_sequential
        self.steps = steps
        self.summary = summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_sequential": self.is_sequential,
            "steps": self.steps,
            "summary": self.summary
        }

class WorkflowPlanner:
    """
    Deconstructs complex, multi-step, or sequenced user instructions into an ordered execution plan.
    """
    
    @staticmethod
    def parse_cron_timing(text: str) -> str:
        """Convert natural language schedule timing to a 5-part cron expression."""
        text_lower = text.lower()
        
        # Check for direct cron expressions (e.g. */2 * * * * or 0 2 * * *)
        cron_match = re.search(r"(\*\/[0-9]+|\*|[0-9]+)\s+(\*\/[0-9]+|\*|[0-9]+)\s+(\*\/[0-9]+|\*|[0-9]+)\s+(\*\/[0-9]+|\*|[0-9]+)\s+(\*\/[0-9]+|\*|[0-9]+)", text)
        if cron_match:
            return cron_match.group(0).strip()

        # Every N minutes
        m_every_min = re.search(r"every\s+([0-9]+)\s*m(in|inute|inutes)?", text_lower)
        if m_every_min:
            mins = int(m_every_min.group(1))
            return f"*/{mins} * * * *"

        # Every minute
        if "every minute" in text_lower or "each minute" in text_lower:
            return "* * * * *"

        # Every N hours
        m_every_hr = re.search(r"every\s+([0-9]+)\s*h(our|ours)?", text_lower)
        if m_every_hr:
            hrs = int(m_every_hr.group(1))
            return f"0 */{hrs} * * *"

        # Hourly
        if "hourly" in text_lower or "every hour" in text_lower:
            return "0 * * * *"

        # Daily at specified time (e.g. 2:00 or 02:00 or 2am)
        m_daily_time = re.search(r"daily\s+at\s+([0-9]{1,2})(:([0-9]{2}))?\s*(am|pm)?", text_lower)
        if m_daily_time:
            hr = int(m_daily_time.group(1))
            minute = int(m_daily_time.group(3)) if m_daily_time.group(3) else 0
            meridiem = m_daily_time.group(4)
            if meridiem == "pm" and hr < 12:
                hr += 12
            elif meridiem == "am" and hr == 12:
                hr = 0
            return f"{minute} {hr} * * *"

        # Default daily midnight
        if "daily" in text_lower:
            return "0 0 * * *"

        return "*/2 * * * *"

    @staticmethod
    def infer_script_filename(prompt: str) -> str:
        """Infer target python script filename from user prompt."""
        # Direct filename pattern
        fn_match = re.search(r"([a-zA-Z0-9_\-]+\.py)", prompt)
        if fn_match:
            return fn_match.group(1)

        prompt_lower = prompt.lower()
        if "met eireann" in prompt_lower or "met éireann" in prompt_lower or "weather" in prompt_lower:
            return "met_eireann_weather.py"
        elif "reconcile" in prompt_lower or "ledger" in prompt_lower:
            return "reconcile.py"
        elif "disk" in prompt_lower or "storage" in prompt_lower:
            return "storage_audit.py"
        elif "service" in prompt_lower or "daemon" in prompt_lower:
            return "service_check.py"
        
        return "script.py"

    def plan(self, prompt: str) -> WorkflowPlan:
        """Analyze prompt and return a sequenced execution plan."""
        prompt_lower = prompt.lower()
        
        # Check for sequenced markers
        has_numbered_steps = bool(re.search(r"(^|\n|\s)(1\.|step\s*1)", prompt_lower) and re.search(r"(^|\n|\s)(2\.|step\s*2)", prompt_lower))
        has_cron_marker = any(k in prompt_lower for k in ["cron", "schedule", "run every", "every 2 min", "every 5 min"])
        has_script_marker = any(k in prompt_lower for k in ["create", "generate", "write", "save"]) and any(k in prompt_lower for k in ["script", "python", ".py"])
        
        # Case 1: Sequenced Script Creation + Cron Deployment
        if (has_numbered_steps or "then" in prompt_lower or "once proven" in prompt_lower or "and schedule" in prompt_lower) and has_script_marker and has_cron_marker:
            filename = self.infer_script_filename(prompt)
            cron_expr = self.parse_cron_timing(prompt)
            
            # Extract script task requirements
            step1_prompt = prompt
            step2_timing = cron_expr
            
            job_name = "Met Éireann Weather Monitor" if "weather" in prompt_lower or "met" in prompt_lower else f"Scheduled {filename}"
            
            steps = [
                {
                    "step": 1,
                    "action": "create_and_test_script",
                    "filename": filename,
                    "description": f"Generate, test, and verify Python script './{filename}' in compute sandbox",
                    "task_prompt": prompt
                },
                {
                    "step": 2,
                    "action": "schedule_cron",
                    "name": job_name,
                    "cron_expression": cron_expr,
                    "target_script": filename,
                    "description": f"Register verified script './{filename}' in Cron Scheduler to run on schedule '{cron_expr}'"
                }
            ]
            
            return WorkflowPlan(
                is_sequential=True,
                steps=steps,
                summary=f"2-Step Sequenced Workflow: (1) Generate & test {filename}; (2) Deploy to cron ({cron_expr})"
            )

        # Case 2: Pure Cron Schedule command
        if has_cron_marker and not has_script_marker:
            cron_expr = self.parse_cron_timing(prompt)
            clean_prompt = re.sub(r"(schedule|in the cron|cron|every [0-9]+ minutes?|daily)", "", prompt, flags=re.IGNORECASE).strip()
            return WorkflowPlan(
                is_sequential=False,
                steps=[{
                    "step": 1,
                    "action": "schedule_cron",
                    "name": "Scheduled Task",
                    "cron_expression": cron_expr,
                    "task_prompt": clean_prompt or prompt
                }],
                summary="Schedule Cron Task"
            )

        # Case 3: Standard single action
        return WorkflowPlan(
            is_sequential=False,
            steps=[{
                "step": 1,
                "action": "execute_single_intent",
                "task_prompt": prompt
            }],
            summary="Standard Task"
        )
