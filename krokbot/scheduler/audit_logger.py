import os
import json
import uuid
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class JobExecution:
    execution_id: str
    job_id: str
    job_name: str
    trigger_type: str  # 'manual' | 'cron'
    trigger_source: str  # 'web_ui' | 'api' | 'apscheduler_daemon'
    start_time: str
    end_time: str
    duration_ms: float
    exit_code: int
    status: str  # 'success' | 'failure'
    stdout: str
    stderr: str
    target_script: Optional[str] = None
    script_sha256: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ExecutionAuditLogger:
    """
    Thread-safe, persistent audit logger for task executions.
    Stores records in append-only JSONL format for compliance, security, and governance.
    """
    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "job_executions.jsonl")
        self._ensure_storage()
        self._in_memory_records: List[Dict[str, Any]] = []
        self._load_recent()

    def _ensure_storage(self):
        os.makedirs(self.log_dir, exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, "a", encoding="utf-8") as f:
                pass

    def _load_recent(self, limit: int = 1000):
        """Preload recent execution records into memory cache for fast API reads."""
        records = []
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line))
                            except Exception:
                                pass
            except Exception:
                pass
        self._in_memory_records = records[-limit:]

    @staticmethod
    def compute_file_sha256(filepath: str) -> Optional[str]:
        """Compute SHA-256 hash of a script for cryptographic verification and audit tracking."""
        if not os.path.exists(filepath):
            return None
        try:
            sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None

    def record_execution(
        self,
        job_id: str,
        job_name: str,
        trigger_type: str,
        start_dt: datetime.datetime,
        end_dt: datetime.datetime,
        exit_code: int,
        stdout: str,
        stderr: str,
        target_script: Optional[str] = None,
        script_path: Optional[str] = None,
        trigger_source: str = "web_ui",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        duration_ms = round((end_dt - start_dt).total_seconds() * 1000, 2)
        status = "success" if exit_code == 0 else "failure"
        script_sha256 = self.compute_file_sha256(script_path) if script_path else None
        exec_id = f"exec-{uuid.uuid4().hex[:8]}"

        record = JobExecution(
            execution_id=exec_id,
            job_id=job_id,
            job_name=job_name,
            trigger_type=trigger_type,
            trigger_source=trigger_source,
            start_time=start_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            end_time=end_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            duration_ms=duration_ms,
            exit_code=exit_code,
            status=status,
            stdout=stdout.strip() if stdout else "",
            stderr=stderr.strip() if stderr else "",
            target_script=target_script,
            script_sha256=script_sha256,
            metadata=metadata or {}
        ).to_dict()

        # Append to disk
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            print(f"[AUDIT LOG ERROR] Failed to write audit record: {e}")

        # Append to memory cache
        self._in_memory_records.append(record)
        if len(self._in_memory_records) > 1000:
            self._in_memory_records = self._in_memory_records[-1000:]

        return record

    def get_job_executions(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Return execution history for a given job, newest first."""
        matching = [r for r in self._in_memory_records if r["job_id"] == job_id]
        return list(reversed(matching[-limit:]))

    def get_all_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return global execution audit log, newest first."""
        return list(reversed(self._in_memory_records[-limit:]))

    def get_execution_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        for r in self._in_memory_records:
            if r["execution_id"] == execution_id:
                return r
        return None
