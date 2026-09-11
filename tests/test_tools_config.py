import pytest
import json
import tempfile
from pathlib import Path
from krokbot.config.tools_config import AgentToolsManager, DEFAULT_TOOLS_CONFIG
from krokbot.agent.tools import ToolRegistry
from krokbot.agent.core import KrokBotAgent

def test_tools_manager_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        
        assert config_path.exists()
        config = mgr.load_config()
        assert "tools" in config
        assert config["version"] == "1.0"
        
        # Check defaults
        assert mgr.is_tool_enabled("python_scripting") is True
        assert mgr.is_tool_enabled("browser_function") is True
        assert mgr.is_tool_enabled("os_bridge") is True
        assert mgr.is_tool_enabled("sandbox_cli") is True
        assert mgr.is_tool_enabled("system_cli") is False  # High risk default off

def test_tools_manager_toggle_and_persist():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))

        # Disable python_scripting
        mgr.set_tool_enabled("python_scripting", False, updated_by="test_runner")
        assert mgr.is_tool_enabled("python_scripting") is False

        # Verify disk persistence
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["tools"]["python_scripting"]["enabled"] is False
        assert data["updated_by"] == "test_runner"

        # Enable system_cli
        mgr.set_tool_enabled("system_cli", True, updated_by="admin_c2")
        assert mgr.is_tool_enabled("system_cli") is True

def test_tools_manager_c2_batch_update():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))

        payload = {
            "tools": {
                "os_bridge": {"enabled": False},
                "system_cli": {"enabled": True}
            }
        }
        res = mgr.update_tools_policy(payload, updated_by="central_c2_api")
        assert res["tools"]["os_bridge"]["enabled"] is False
        assert res["tools"]["system_cli"]["enabled"] is True
        assert res["updated_by"] == "central_c2_api"

def test_tool_registry_governance_interception():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        registry = ToolRegistry(tools_manager=mgr)

        # 1. Disable python_scripting
        mgr.set_tool_enabled("python_scripting", False)
        res = registry.run_sandbox_script("print('hello')")
        assert res["exit_code"] == 126
        assert "[SECURITY GOVERNANCE ERROR]" in res["stderr"]

        res_file = registry.run_sandbox_file("script.py")
        assert res_file["exit_code"] == 126
        assert "[SECURITY GOVERNANCE ERROR]" in res_file["stderr"]

        # 2. Disable browser_function
        mgr.set_tool_enabled("browser_function", False)
        browser_res = registry.run_browser_action("wait", duration=0.1)
        assert browser_res["status"] == "error"
        assert "[SECURITY GOVERNANCE ERROR]" in browser_res["output"]

        # 3. Disable os_bridge
        mgr.set_tool_enabled("os_bridge", False)
        metrics_res = registry.query_host_metrics("summary")
        assert metrics_res.get("error") == "SECURITY_POLICY_VIOLATION"
        assert "[SECURITY GOVERNANCE ERROR]" in metrics_res.get("message", "")

        # 4. Check system_cli (disabled by default)
        cli_res = registry.run_system_cli("echo test")
        assert cli_res["exit_code"] == 126
        assert "[SECURITY GOVERNANCE ERROR]" in cli_res["stderr"]

def test_agent_policy_control_python_scripting():
    """Validate enablement and disablement enforcement of python_scripting policy control."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        agent = KrokBotAgent(tools_manager=mgr)

        # 1. When python_scripting is disabled
        mgr.set_tool_enabled("python_scripting", False)
        res_disabled = agent.run_task("generate python script reconcile.py", save_mode="one_time")
        assert res_disabled["status"] == "blocked"
        assert res_disabled["exit_code"] == 126
        assert "Python Scripting" in res_disabled["report"]

        # 2. When python_scripting is enabled
        mgr.set_tool_enabled("python_scripting", True)
        agent._generate_script = lambda fn, tp, sp: "print('reconcile script success')\n"
        agent.tools.sandbox.execute_file = lambda fn: {"exit_code": 0, "stdout": "reconcile script success", "stderr": ""}
        res_enabled = agent.run_task("generate python script reconcile.py", save_mode="one_time")
        assert res_enabled["status"] == "success"
        assert res_enabled["exit_code"] == 0

def test_agent_policy_control_os_bridge():
    """Validate enablement and disablement enforcement of os_bridge (host hardware telemetry) policy control."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        agent = KrokBotAgent(tools_manager=mgr)

        # 1. When os_bridge is disabled
        mgr.set_tool_enabled("os_bridge", False)
        res_disabled = agent.run_task("Check the disk capacity of the underlying system")
        assert res_disabled["status"] == "blocked"
        assert res_disabled.get("exit_code") == 126
        assert "OS Bridge" in res_disabled["report"]
        assert "SECURITY_POLICY_VIOLATION" in str(res_disabled.get("metrics", {}))

        # 2. When os_bridge is enabled
        mgr.set_tool_enabled("os_bridge", True)
        # Mock bridge query response and LLM for unit test isolation
        agent.client.chat = lambda msgs: {"message": {"content": "System storage audit: Final Answer: Done"}}
        agent.tools.query_host_metrics = lambda ep: [{"device": "C:", "total_gb": 1000.0, "used_gb": 400.0, "free_gb": 600.0, "percent_used": 40.0}] if ep == "storage" else {"cpu_count": 8}
        res_enabled = agent.run_task("Check the disk capacity of the underlying system")
        assert res_enabled["status"] == "success"
        assert res_enabled.get("storage") is not None

def test_agent_policy_control_browser_function():
    """Validate enablement and disablement enforcement of browser_function policy control."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        agent = KrokBotAgent(tools_manager=mgr)

        # 1. When browser_function is disabled
        mgr.set_tool_enabled("browser_function", False)
        res_disabled = agent.run_task("what is the weather in Dublin on met eireann website?")
        assert res_disabled["status"] == "blocked"
        assert "Browser Function" in res_disabled["report"]

        # 2. When browser_function is enabled
        mgr.set_tool_enabled("browser_function", True)
        agent.client.chat = lambda msgs: {"message": {"content": "Weather in Dublin is 17C Cloudy. Final Answer: Done"}}
        agent.tools.run_browser_action = lambda action, **kw: {"status": "success", "output": "Weather: 17C Cloudy"}
        agent.tools.run_sandbox_script = lambda script: {"exit_code": 0, "stdout": "Dublin 17C Cloudy", "stderr": ""}
        res_enabled = agent.run_task("what is the weather in Dublin on met eireann website?")
        assert res_enabled["status"] == "success"

def test_agent_policy_control_sandbox_cli():
    """Validate enablement and disablement enforcement of sandbox_cli policy control."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        agent = KrokBotAgent(tools_manager=mgr)

        # 1. When sandbox_cli is disabled
        mgr.set_tool_enabled("sandbox_cli", False)
        res_disabled = agent.run_task("write a script test_cli.py", save_mode="one_time")
        assert res_disabled["status"] == "blocked"
        assert res_disabled["exit_code"] == 126
        assert "Sandbox CLI" in res_disabled["report"]

        # 2. When sandbox_cli is enabled
        mgr.set_tool_enabled("sandbox_cli", True)
        agent._generate_script = lambda fn, tp, sp: "print('test_cli script success')\n"
        agent.tools.sandbox.execute_file = lambda fn: {"exit_code": 0, "stdout": "Script ran successfully", "stderr": ""}
        res_enabled = agent.run_task("write a script test_cli.py", save_mode="one_time")
        assert res_enabled["status"] == "success"
        assert res_enabled["exit_code"] == 0

def test_agent_policy_control_system_cli():
    """Validate enablement and disablement enforcement of system_cli (host OS CLI) policy control."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_tools.json"
        mgr = AgentToolsManager(config_path=str(config_path))
        agent = KrokBotAgent(tools_manager=mgr)

        # 1. When system_cli is disabled (default)
        mgr.set_tool_enabled("system_cli", False)
        res_disabled = agent.run_task("run on host os CLI: dir")
        assert res_disabled["status"] == "blocked"
        assert res_disabled["exit_code"] == 126
        assert "System CLI Functions" in res_disabled["report"]

        # 2. When system_cli is enabled
        mgr.set_tool_enabled("system_cli", True)
        agent.tools.run_system_cli = lambda cmd: {"exit_code": 0, "stdout": "Directory of C:\\\nfile.txt", "stderr": ""}
        res_enabled = agent.run_task("run on host os CLI: dir")
        assert res_enabled["status"] == "success"
        assert "Directory of C:" in res_enabled["report"]

