import pytest
import os
import json
from krokbot.scheduler.manager import CronSchedulerManager

def test_cron_scheduler_manager_add_and_list(tmp_path):
    json_path = tmp_path / "schedules.json"
    manager = CronSchedulerManager(storage_path=str(json_path))
    
    item = manager.add_schedule(
        name="Test Storage Check",
        cron_expression="0 * * * *",
        prompt="Inspect storage partitions"
    )
    
    assert item["name"] == "Test Storage Check"
    assert item["cron_expression"] == "0 * * * *"
    assert os.path.exists(json_path)
    
    schedules = manager.get_all_schedules()
    assert len(schedules) == 1
    assert schedules[0]["id"] == item["id"]

def test_cron_scheduler_manager_remove(tmp_path):
    json_path = tmp_path / "schedules.json"
    manager = CronSchedulerManager(storage_path=str(json_path))
    item = manager.add_schedule("Temp Task", "*/5 * * * *", "Run temp check")
    
    manager.remove_schedule(item["id"])
    assert len(manager.get_all_schedules()) == 0
