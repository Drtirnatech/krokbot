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

@patch("krokbot.agent.llamacpp_client.LlamaCppClient.chat")
@patch("krokbot.agent.tools.ToolRegistry.query_host_metrics")
def test_agent_react_loop(mock_metrics, mock_chat):
    mock_metrics.return_value = {"cpu_percent": 15.0}
    mock_chat.return_value = {
        "message": {
            "content": "Final Answer: Workstation health check complete. Storage and CPU levels are normal."
        }
    }
    agent = KrokBotAgent(model="qwen3-4b")
    result = agent.run_task("Check system health")
    assert "Workstation health check complete" in result["report"]

def test_tool_registry_browser_action():
    registry = ToolRegistry()
    res = registry.run_browser_action("wait", duration=0.1)
    assert res["status"] == "success"
    assert "waited" in res["output"]

def test_agent_host_cli_intent_classification():
    agent = KrokBotAgent()
    assert agent._classify_intent("run curl --version on the host systems cli") == "host_cli"
    assert agent._classify_intent("run curl --version on the host system cli") == "host_cli"
    assert agent._classify_intent("run powershell.exe -Command 'whoami' on my host system cli") == "host_cli"
    assert agent._classify_intent("run on my host: ipconfig") == "host_cli"
    assert agent._classify_intent("run on host: ipconfig") == "host_cli"
    assert agent._classify_intent("on the host cli run hostname") == "host_cli"
    assert agent._classify_intent("check weather in dublin") == "web_query"

def test_agent_extract_host_command():
    agent = KrokBotAgent()
    assert agent._extract_host_command("run curl --version on the host systems cli") == "curl --version"
    assert agent._extract_host_command("run `curl --version` on host cli") == "curl --version"
    assert agent._extract_host_command("on the host systems cli run curl --version") == "curl --version"
    assert agent._extract_host_command("curl --version") == "curl --version"
    cmd_ps = "powershell.exe -Command '$env:COMPUTERNAME; Get-CimInstance Win32_OperatingSystem | Select Caption,Version; whoami'"
    assert agent._extract_host_command(f"run {cmd_ps} on my host system cli") == cmd_ps
    assert agent._extract_host_command("run 'dir C:\\' on my host cli") == "dir C:\\"

@patch("krokbot.agent.tools.ToolRegistry.run_system_cli")
def test_agent_host_cli_execution_enabled(mock_run_cli):
    mock_run_cli.return_value = {
        "status": "success",
        "exit_code": 0,
        "stdout": "curl 8.21.0 (Windows) libcurl/8.21.0\nProtocols: dict file ftp http https",
        "stderr": ""
    }
    agent = KrokBotAgent()
    result = agent.run_task("run curl --version on the host systems cli")
    assert result["status"] == "success"
    assert result["exit_code"] == 0
    assert result["command"] == "curl --version"
    assert "curl 8.21.0" in result["report"]
    mock_run_cli.assert_called_once_with("curl --version")

def test_agent_host_cli_execution_disabled():
    from krokbot.config.tools_config import AgentToolsManager
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "agent_tools.json"
        mgr = AgentToolsManager(config_path=str(cfg))
        mgr.set_tool_enabled("system_cli", False)
        agent = KrokBotAgent(tools_manager=mgr)
        result = agent.run_task("run curl --version on the host systems cli")
        assert result["status"] == "blocked"
        assert result["exit_code"] == 126
        assert "System CLI Functions (Host OS)' tool is disabled" in result["report"]

def test_parse_thinking_and_output():
    agent = KrokBotAgent()
    raw = "<think>\nAnalyzing the question step by step.\nConsidering physics laws.\n</think>\n\nThe sky is blue due to Rayleigh scattering.\n\nFinal Answer: Blue light scatters most."
    parsed = agent._parse_thinking_and_output(raw)
    assert "Analyzing the question step by step" in parsed["thinking"]
    assert "Considering physics laws" in parsed["thinking"]
    assert "<think>" not in parsed["output"]
    assert "</think>" not in parsed["output"]
    assert "The sky is blue due to Rayleigh scattering." in parsed["output"]

@patch("krokbot.agent.llamacpp_client.LlamaCppClient.chat")
def test_agent_show_thinking_option(mock_chat):
    mock_chat.return_value = {
        "message": {
            "content": "<think>\nInternal reasoning steps here.\n</think>\n\nFinal Answer: Clean output without thoughts."
        }
    }
    agent = KrokBotAgent()
    
    # 1. When show_thinking is False, report must NOT contain <think> tags
    res_no_think = agent.run_task("Explain something", show_thinking=False)
    assert "<think>" not in res_no_think["report"]
    assert res_no_think["report"] == "Final Answer: Clean output without thoughts."
    assert "Internal reasoning steps here." in res_no_think["thinking"]
    assert res_no_think["show_thinking"] is False

    # 2. When show_thinking is True, report and thinking are preserved
    res_think = agent.run_task("Explain something", show_thinking=True)
    assert "<think>" in res_think["report"]
    assert "Internal reasoning steps here." in res_think["thinking"]
    assert res_think["show_thinking"] is True



