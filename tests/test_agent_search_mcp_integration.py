# tests/test_agent_search_mcp_integration.py
import pytest
from unittest.mock import patch, MagicMock
from krokbot.agent.core import KrokBotAgent
from krokbot.config.tools_config import AgentToolsManager

def test_agent_search_mcp_governance_block(tmp_path):
    config_file = tmp_path / "agent_tools.json"
    mgr = AgentToolsManager(str(config_file))
    mgr.set_tool_enabled("local_search_mcp", False)
    
    agent = KrokBotAgent(tools_manager=mgr)
    res = agent.run_task("search online for latest Dublin weather")
    assert res.get("status") == "blocked"
    assert "local_search_mcp" in res.get("report", "").lower() or "search" in res.get("report", "").lower()

def test_agent_search_mcp_success_routing(tmp_path):
    config_file = tmp_path / "agent_tools.json"
    mgr = AgentToolsManager(str(config_file))
    mgr.set_tool_enabled("local_search_mcp", True)

    agent = KrokBotAgent(tools_manager=mgr)
    with patch("client.mcp_docker_wrapper.McpDockerClientWrapper.search") as mock_search, \
         patch.object(agent.client, "chat") as mock_chat:
        
        mock_search.return_value = {
            "status": "success",
            "markdown": "### Local Web Search: Dublin Weather\nTemperature: 15°C"
        }
        mock_chat.return_value = {
            "message": {"content": "Dublin weather is currently 15°C.\nFinal Answer: Dublin is 15°C."}
        }
        res = agent.run_task("search the web for Dublin weather updates")
        assert res.get("status") == "success"
        assert "Dublin" in res.get("report", "")
        mock_search.assert_called_once()
