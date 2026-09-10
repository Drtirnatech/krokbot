import pytest
import os
from unittest.mock import patch
from krokbot.agent.core import KrokBotAgent
from krokbot.dashboard.server import export_health_report

@patch("krokbot.agent.ollama_client.OllamaClient.chat")
@patch("krokbot.agent.tools.ToolRegistry.query_host_metrics")
def test_end_to_end_agent_flow(mock_metrics, mock_chat, tmp_path):
    mock_metrics.return_value = {"cpu_percent": 18.0, "memory_percent": 42.0, "os_info": "Windows 11"}
    mock_chat.return_value = {
        "message": {
            "content": "Final Answer: All workstation systems, storage, and active services operating within healthy thresholds."
        }
    }

    agent = KrokBotAgent()
    result = agent.run_task("Perform workstation sanity health check")
    
    assert "status" in result
    assert result["status"] == "success"
    
    report_file = tmp_path / "krokbot_health_report.md"
    export_health_report(str(report_file), result["report"], result["metrics"])
    assert os.path.exists(report_file)
    assert "healthy thresholds" in report_file.read_text()
