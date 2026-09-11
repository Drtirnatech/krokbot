import pytest
from unittest.mock import patch, MagicMock
from krokbot.agent.core import KrokBotAgent
from krokbot.agent.planner import WorkflowPlanner
from krokbot.scheduler.manager import CronSchedulerManager

def test_workflow_planner_sequenced_prompt():
    planner = WorkflowPlanner()
    prompt = (
        "1. create and save a python script that retireves the weather forecast from met eireann's website and display it on the agent terminal screeen.\n"
        "2. place that script in the cron to run every 2 minutes."
    )
    plan = planner.plan(prompt)
    assert plan.is_sequential is True
    assert len(plan.steps) == 2
    assert plan.steps[0]["action"] == "create_and_test_script"
    assert plan.steps[0]["filename"] == "met_eireann_weather.py"
    assert plan.steps[1]["action"] == "schedule_cron"
    assert plan.steps[1]["cron_expression"] == "*/2 * * * *"
    assert plan.steps[1]["target_script"] == "met_eireann_weather.py"

@patch("krokbot.agent.llamacpp_client.LlamaCppClient.chat")
def test_agent_sequenced_workflow_execution(mock_chat, tmp_path):
    mock_weather_code = (
        "import sys\n"
        "print('[MET EIREANN] Forecast: Rain spreading eastwards, highs of 14C.')\n"
        "sys.exit(0)\n"
    )
    mock_chat.return_value = {
        "message": {
            "content": f"Here is the script:\n```python\n{mock_weather_code}\n```"
        }
    }

    scheduler = CronSchedulerManager(storage_path=str(tmp_path / "schedules.json"))
    agent = KrokBotAgent(scheduler_manager=scheduler)
    agent.tools.sandbox.workspace_dir = tmp_path

    prompt = (
        "1. create and save a python script that retireves the weather forecast from met eireann's website and display it on the agent terminal screeen.\n"
        "2. place that script in the cron to run every 2 minutes."
    )

    result = agent.run_task(prompt)
    
    assert result["status"] == "success"
    assert result["exit_code"] == 0
    assert "Forecast: Rain spreading eastwards" in result["sandbox_output"]["stdout"]
    assert "Sequenced Workflow Execution Plan & Results" in result["report"]
    assert "*/2 * * * *" in result["report"]
    
    # Verify script file exists
    assert (tmp_path / "met_eireann_weather.py").exists()

    # Verify cron job is registered
    schedules = scheduler.get_all_schedules()
    assert len(schedules) == 1
    assert schedules[0]["cron_expression"] == "*/2 * * * *"
    assert schedules[0]["target_script"] == "met_eireann_weather.py"
