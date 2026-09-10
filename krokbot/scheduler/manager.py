import os
import json
import uuid
import datetime
from typing import List, Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

class CronSchedulerManager:
    """
    Manages persistent cron schedules backed by data/schedules.json and APScheduler.
    """
    def __init__(self, storage_path: str = "data/schedules.json"):
        self.storage_path = storage_path
        self.scheduler = BackgroundScheduler()
        self.schedules: List[Dict[str, Any]] = []
        self._ensure_storage()
        self.load_schedules()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_schedules(self):
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self.schedules = json.load(f)
        except Exception:
            self.schedules = []

    def save_schedules(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.schedules, f, indent=2)

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def get_all_schedules(self) -> List[Dict[str, Any]]:
        return self.schedules

    def add_schedule(self, name: str, cron_expression: str, prompt: str, job_func=None) -> Dict[str, Any]:
        schedule_id = f"cron-{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now().isoformat()
        
        item = {
            "id": schedule_id,
            "name": name,
            "cron_expression": cron_expression,
            "prompt": prompt,
            "enabled": True,
            "created_at": now_str,
            "last_run": None,
            "next_run": None
        }
        
        self.schedules.append(item)
        self.save_schedules()

        if job_func and self.scheduler.running:
            try:
                trigger = CronTrigger.from_crontab(cron_expression)
                self.scheduler.add_job(
                    job_func,
                    trigger=trigger,
                    id=schedule_id,
                    kwargs={"task_prompt": prompt, "schedule_id": schedule_id}
                )
            except Exception as e:
                print(f"[SCHEDULER] Warning: Failed to parse cron expression '{cron_expression}': {e}")

        return item

    def remove_schedule(self, schedule_id: str) -> bool:
        self.schedules = [s for s in self.schedules if s["id"] != schedule_id]
        self.save_schedules()
        if self.scheduler.running and self.scheduler.get_job(schedule_id):
            self.scheduler.remove_job(schedule_id)
        return True
