import pytest
from unittest.mock import patch, MagicMock
from krokbot.agent.tools import ToolRegistry
from krokbot.agent.core import KrokBotAgent
from krokbot.scheduler.manager import CronSchedulerManager

@patch("httpx.Client.get")
def test_tool_registry(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"cpu_percent": 12.5, "memory_percent": 40.0}
    mock_get.return_value = mock_resp

    registry = ToolRegistry()
    summary = registry.query_host_metrics("summary")
    assert summary["cpu_percent"] == 12.5

def test_schedule_cron_task_tool(tmp_path):
    json_path = tmp_path / "schedules.json"
    scheduler = CronSchedulerManager(storage_path=str(json_path))
    registry = ToolRegistry(scheduler_manager=scheduler)
    
    result = registry.schedule_cron_task("Daily Audit", "0 0 * * *", "Perform daily system check")
    assert result["status"] == "success"
    assert result["schedule"]["name"] == "Daily Audit"

@patch("krokbot.agent.ollama_client.OllamaClient.chat")
@patch("krokbot.agent.tools.ToolRegistry.query_host_metrics")
def test_agent_react_loop(mock_metrics, mock_chat):
    mock_metrics.return_value = {"cpu_percent": 15.0}
    mock_chat.return_value = {
        "message": {
            "content": "Final Answer: Workstation health check complete. Storage and CPU levels are normal."
        }
    }
    agent = KrokBotAgent(model="llama3.2")
    result = agent.run_task("Check system health")
    assert "Workstation health check complete" in result["report"]

def test_tool_registry_browser_action():
    registry = ToolRegistry()
    res = registry.run_browser_action("wait", duration=0.1)
    assert res["status"] == "success"
    assert "waited" in res["output"]

