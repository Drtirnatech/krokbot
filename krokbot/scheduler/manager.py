import os
import json
import uuid
import datetime
from typing import List, Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from krokbot.sandbox.executor import SandboxExecutor
from krokbot.scheduler.audit_logger import ExecutionAuditLogger

class CronSchedulerManager:
    """
    Manages persistent cron schedules backed by data/schedules.json, APScheduler,
    and a persistent execution audit log (data/logs/job_executions.jsonl) for governance and security.
    """
    def __init__(self, storage_path: str = "data/schedules.json", default_job_func=None, sandbox_executor: Optional[SandboxExecutor] = None):
        self.storage_path = storage_path
        self.scheduler = BackgroundScheduler()
        self.schedules: List[Dict[str, Any]] = []
        self.default_job_func = default_job_func
        self.job_runners: Dict[str, Any] = {}
        self.sandbox = sandbox_executor or SandboxExecutor()
        
        log_dir = os.path.join(os.path.dirname(self.storage_path) or "data", "logs")
        self.audit_logger = ExecutionAuditLogger(log_dir=log_dir)

        self._ensure_storage()
        self.load_schedules()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_schedules(self):
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self.schedules = json.load(f)
        except Exception:
            self.schedules = []

    def reload_schedules(self) -> List[Dict[str, Any]]:
        self.load_schedules()
        return self.get_all_schedules()

    def save_schedules(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.schedules, f, indent=2)

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
        for item in self.schedules:
            if item.get("enabled", True):
                self._register_job(item)

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _register_job(self, item: Dict[str, Any], job_func=None):
        if job_func:
            self.job_runners[item["id"]] = job_func

        if not self.scheduler.running:
            return
        
        job_id = item["id"]
        if self.scheduler.get_job(job_id):
            return

        try:
            trigger = CronTrigger.from_crontab(item["cron_expression"])
            self.scheduler.add_job(
                self._execute_wrapper,
                trigger=trigger,
                id=job_id,
                kwargs={"schedule_id": job_id}
            )
        except Exception as e:
            print(f"[SCHEDULER] Warning: Failed to parse cron expression '{item.get('cron_expression')}': {e}")

    def _execute_wrapper(self, schedule_id: str):
        target = None
        for s in self.schedules:
            if s["id"] == schedule_id:
                target = s
                break
        if not target:
            return

        try:
            return self._execute_job_with_audit(target, trigger_type="cron", source="apscheduler_daemon")
        except Exception as e:
            print(f"[SCHEDULER] Job execution error ({schedule_id}): {e}")

    def _execute_job_with_audit(
        self,
        item: Dict[str, Any],
        trigger_type: str = "cron",
        source: str = "apscheduler_daemon"
    ) -> Dict[str, Any]:
        """
        Unified execution pipeline: executes code, records SHA-256 integrity hash,
        captures stdout/stderr/exit_code/duration, and logs to persistent audit store.
        """
        job_id = item["id"]
        job_name = item.get("name", "Scheduled Task")
        target_script = item.get("target_script")
        prompt = item.get("prompt", "")

        start_dt = datetime.datetime.now()
        stdout = ""
        stderr = ""
        exit_code = 0
        script_path = None

        if target_script:
            script_path = str(self.sandbox._resolve_path(target_script))

        # 1. Custom runner if registered
        runner = self.job_runners.get(job_id)
        if runner:
            try:
                res = runner(prompt, schedule_id=job_id)
                if isinstance(res, dict):
                    exit_code = res.get("exit_code", 0)
                    stdout = res.get("stdout", "")
                    stderr = res.get("stderr", "")
                    if "error" in res and not stderr:
                        stderr = str(res["error"])
                elif isinstance(res, str):
                    stdout = res
            except Exception as e:
                exit_code = 1
                stderr = str(e)
        # 2. Target script execution via compute sandbox
        elif target_script:
            res = self.sandbox.execute_file(target_script)
            exit_code = res.get("exit_code", 0)
            stdout = res.get("stdout", "")
            stderr = res.get("stderr", "")
        # 3. Default job function fallback
        elif self.default_job_func:
            try:
                res = self.default_job_func(prompt)
                if isinstance(res, dict):
                    exit_code = res.get("exit_code", 0)
                    stdout = res.get("report") or res.get("stdout") or str(res)
                    stderr = res.get("stderr", "")
                else:
                    stdout = str(res)
            except Exception as e:
                exit_code = 1
                stderr = str(e)
        else:
            stdout = f"Job '{job_name}' executed (no script bound)."

        end_dt = datetime.datetime.now()
        duration_ms = round((end_dt - start_dt).total_seconds() * 1000, 2)
        status = "success" if exit_code == 0 else "failure"

        # Record in persistent audit logger
        audit_record = self.audit_logger.record_execution(
            job_id=job_id,
            job_name=job_name,
            trigger_type=trigger_type,
            start_dt=start_dt,
            end_dt=end_dt,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            target_script=target_script,
            script_path=script_path,
            trigger_source=source
        )

        # Update schedule item state
        now_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        item["last_run"] = now_str
        item["last_status"] = status
        item["last_exit_code"] = exit_code
        item["last_duration_ms"] = duration_ms
        item["last_execution_id"] = audit_record["execution_id"]
        self.save_schedules()

        print(f"[AUDIT LOGGED] Job: '{job_name}' ({job_id}) | Trigger: {trigger_type} ({source}) | Status: {status} (Exit {exit_code}) | Duration: {duration_ms}ms")
        return audit_record

    def get_all_schedules(self) -> List[Dict[str, Any]]:
        results = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for s in self.schedules:
            item = dict(s)
            try:
                job = self.scheduler.get_job(s["id"]) if self.scheduler.running else None
                if job and job.next_run_time:
                    item["next_run"] = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    trigger = CronTrigger.from_crontab(s["cron_expression"])
                    next_time = trigger.get_next_fire_time(None, now_utc)
                    if next_time:
                        item["next_run"] = next_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            results.append(item)
        return results

    def add_schedule(
        self,
        name: str,
        cron_expression: str,
        prompt: str,
        target_script: Optional[str] = None,
        job_func=None
    ) -> Dict[str, Any]:
        schedule_id = f"cron-{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        item = {
            "id": schedule_id,
            "name": name,
            "cron_expression": cron_expression,
            "prompt": prompt,
            "target_script": target_script,
            "enabled": True,
            "created_at": now_str,
            "last_run": None,
            "next_run": None,
            "last_status": "pending",
            "last_exit_code": None,
            "last_duration_ms": None
        }
        
        self.schedules.append(item)
        self.save_schedules()
        self._register_job(item, job_func=job_func)

        try:
            trigger = CronTrigger.from_crontab(cron_expression)
            next_time = trigger.get_next_fire_time(None, datetime.datetime.now(datetime.timezone.utc))
            if next_time:
                item["next_run"] = next_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        return item

    def remove_schedule(self, schedule_id: str) -> bool:
        initial_len = len(self.schedules)
        self.schedules = [s for s in self.schedules if s["id"] != schedule_id]
        found = len(self.schedules) < initial_len
        
        if found:
            self.save_schedules()
            if schedule_id in self.job_runners:
                del self.job_runners[schedule_id]
            if self.scheduler.running and self.scheduler.get_job(schedule_id):
                try:
                    self.scheduler.remove_job(schedule_id)
                except Exception:
                    pass
        return found

    def clear_all_schedules(self) -> int:
        count = len(self.schedules)
        self.schedules = []
        self.job_runners = {}
        self.save_schedules()
        if self.scheduler.running:
            for job in list(self.scheduler.get_jobs()):
                if job.id.startswith("cron-"):
                    try:
                        self.scheduler.remove_job(job.id)
                    except Exception:
                        pass
        return count

    def trigger_schedule(self, schedule_id: str, source: str = "web_ui") -> Optional[Dict[str, Any]]:
        target = None
        for s in self.schedules:
            if s["id"] == schedule_id:
                target = s
                break
        if not target:
            return None

        audit_record = self._execute_job_with_audit(target, trigger_type="manual", source=source)
        return {
            "schedule": target,
            "execution": audit_record
        }

    def get_job_executions(self, schedule_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.audit_logger.get_job_executions(schedule_id, limit=limit)

    def get_all_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.audit_logger.get_all_executions(limit=limit)

    def get_execution_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        return self.audit_logger.get_execution_by_id(execution_id)

