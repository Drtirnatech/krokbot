import os
import json
import datetime
import pytest
from krokbot.scheduler.audit_logger import ExecutionAuditLogger, JobExecution
from krokbot.scheduler.manager import CronSchedulerManager
from krokbot.sandbox.executor import SandboxExecutor

def test_audit_logger_record_and_retrieve(tmp_path):
    log_dir = tmp_path / "logs"
    logger = ExecutionAuditLogger(log_dir=str(log_dir))

    # Test file sha256 calculation
    test_file = tmp_path / "test_script.py"
    test_file.write_text("print('audit hello')", encoding="utf-8")
    sha = logger.compute_file_sha256(str(test_file))
    assert sha is not None
    assert len(sha) == 64

    # Record execution
    start = datetime.datetime.now()
    end = start + datetime.timedelta(milliseconds=150)
    record = logger.record_execution(
        job_id="cron-test-01",
        job_name="Test Task",
        trigger_type="manual",
        start_dt=start,
        end_dt=end,
        exit_code=0,
        stdout="Forecast: Sunny 20C",
        stderr="",
        target_script="test_script.py",
        script_path=str(test_file),
        trigger_source="web_ui"
    )

    assert record["job_id"] == "cron-test-01"
    assert record["status"] == "success"
    assert record["duration_ms"] >= 140
    assert record["script_sha256"] == sha
    assert record["stdout"] == "Forecast: Sunny 20C"

    # Query by job ID
    job_execs = logger.get_job_executions("cron-test-01")
    assert len(job_execs) == 1
    assert job_execs[0]["execution_id"] == record["execution_id"]

    # Query by execution ID
    single = logger.get_execution_by_id(record["execution_id"])
    assert single is not None
    assert single["job_name"] == "Test Task"

    # Query global executions
    all_execs = logger.get_all_executions()
    assert len(all_execs) >= 1

    # Test persistence by instantiating new logger on same log_dir
    reloaded_logger = ExecutionAuditLogger(log_dir=str(log_dir))
    reloaded_execs = reloaded_logger.get_job_executions("cron-test-01")
    assert len(reloaded_execs) == 1
    assert reloaded_execs[0]["execution_id"] == record["execution_id"]

def test_scheduler_manager_audit_execution(tmp_path):
    schedules_json = tmp_path / "schedules.json"
    sandbox = SandboxExecutor(workspace_dir=str(tmp_path / "sandbox"))
    sandbox.write_file("worker.py", "import sys; print('Worker running'); sys.exit(0)")

    manager = CronSchedulerManager(storage_path=str(schedules_json), sandbox_executor=sandbox)
    item = manager.add_schedule(
        name="Worker Job",
        cron_expression="*/5 * * * *",
        prompt="Run worker",
        target_script="worker.py"
    )

    # Trigger manually
    result = manager.trigger_schedule(item["id"], source="web_ui")
    assert result is not None
    execution = result["execution"]
    assert execution["job_id"] == item["id"]
    assert execution["exit_code"] == 0
    assert "Worker running" in execution["stdout"]
    assert execution["status"] == "success"
    assert execution["script_sha256"] is not None

    # Check updated schedule metadata
    schedules = manager.get_all_schedules()
    updated_item = next(s for s in schedules if s["id"] == item["id"])
    assert updated_item["last_status"] == "success"
    assert updated_item["last_exit_code"] == 0
    assert updated_item["last_duration_ms"] is not None

    # Verify audit retrieval through manager
    history = manager.get_job_executions(item["id"])
    assert len(history) == 1
    assert history[0]["execution_id"] == execution["execution_id"]
