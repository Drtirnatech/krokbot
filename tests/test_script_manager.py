import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from krokbot.scripts.manager import ScriptAssetManager
from krokbot.sandbox.executor import SandboxExecutor
from krokbot.agent.core import KrokBotAgent
from krokbot.dashboard.server import app as dashboard_app, set_agent_instance
from krokbot.bridge.main import app as bridge_app

def test_script_manager_save_and_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ScriptAssetManager(scripts_dir=tmpdir)
        code = "print('Hello from saved script')\n"
        purpose = "Test automated script for workspace verification."

        res = mgr.save_script(name="sample_tool.py", code=code, purpose=purpose, category="Testing")
        assert res["status"] == "success"
        assert res["name"] == "sample_tool.py"
        assert res["markup_filename"] == "sample_tool.md"

        py_file = Path(tmpdir) / "sample_tool.py"
        md_file = Path(tmpdir) / "sample_tool.md"
        assert py_file.exists()
        assert md_file.exists()

        md_content = md_file.read_text(encoding="utf-8")
        assert "Test automated script for workspace verification." in md_content
        assert res["sha256"] in md_content

        # List scripts
        scripts = mgr.list_scripts()
        assert len(scripts) == 1
        item = scripts[0]
        assert item["name"] == "sample_tool.py"
        assert item["has_markup"] is True
        assert item["category"] == "Testing"
        assert "Test automated script" in item["purpose_summary"]

def test_script_manager_get_and_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ScriptAssetManager(scripts_dir=tmpdir)
        code = "x = 42\nprint(x)\n"
        mgr.save_script(name="calc.py", code=code, purpose="Simple 42 calculator")

        item = mgr.get_script("calc.py")
        assert item is not None
        assert item["code"] == code
        assert item["has_markup"] is True
        assert "Simple 42 calculator" in item["markdown"]

        # Delete
        deleted = mgr.delete_script("calc.py")
        assert deleted is True
        assert not (Path(tmpdir) / "calc.py").exists()
        assert not (Path(tmpdir) / "calc.md").exists()
        assert len(mgr.list_scripts()) == 0

def test_script_manager_run_in_sandbox():
    with tempfile.TemporaryDirectory() as scripts_dir, tempfile.TemporaryDirectory() as sandbox_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        sandbox = SandboxExecutor(workspace_dir=sandbox_dir)

        code = "print('TOKEN_SANDBOX_SUCCESS_99')\n"
        mgr.save_script(name="token_run.py", code=code, purpose="Token runner test")

        res = mgr.run_script("token_run.py", sandbox)
        assert res["exit_code"] == 0
        assert "TOKEN_SANDBOX_SUCCESS_99" in res["stdout"]

def test_script_manager_run_stream_in_sandbox():
    with tempfile.TemporaryDirectory() as scripts_dir, tempfile.TemporaryDirectory() as sandbox_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        sandbox = SandboxExecutor(workspace_dir=sandbox_dir)

        code = "print('STEP_1_START')\nprint('STEP_2_PROGRESS')\nprint('STEP_3_DONE')\n"
        mgr.save_script(name="stream_demo.py", code=code, purpose="CLI streaming test")

        events = list(mgr.run_script_stream("stream_demo.py", sandbox))
        event_types = [e["event"] for e in events]
        assert "init" in event_types
        assert "start" in event_types
        assert "output" in event_types
        assert "complete" in event_types

        # Verify command line perspective details
        start_ev = next(e for e in events if e["event"] == "start")
        assert "python3 -u stream_demo.py" in start_ev["command"]
        assert "sandbox" in start_ev["cwd"].lower() or Path(start_ev["cwd"]).exists()

        complete_ev = next(e for e in events if e["event"] == "complete")
        assert complete_ev["exit_code"] == 0
        assert "STEP_1_START" in complete_ev["stdout"]
        assert "STEP_2_PROGRESS" in complete_ev["stdout"]
        assert "STEP_3_DONE" in complete_ev["stdout"]

def test_agent_script_interactive_prompt_and_save():
    with tempfile.TemporaryDirectory() as scripts_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        agent = KrokBotAgent(script_manager=mgr)
        agent._generate_script = lambda fn, tp, sp: "print('Tax calculation completed: $1,250')\n"

        # 1. Unspecified persistence -> asks user
        res1 = agent.run_task("generate python script to calculate taxes in tax_calc.py")
        assert res1["status"] == "ask_confirmation"
        assert res1["requires_confirmation"] is True
        assert "tax_calc.py" in res1["question"]

        # 2. User confirms with save_mode = 'saved'
        res2 = agent.run_task("generate python script to calculate taxes in tax_calc.py", save_mode="saved")
        assert res2["status"] == "success"
        assert res2["save_mode"] == "saved"
        assert "data/scripts/tax_calc.py" in res2["report"]
        assert "tax_calc.md" in res2["report"]

        # Verify saved in manager
        saved = mgr.get_script("tax_calc.py")
        assert saved is not None
        assert saved["has_markup"] is True

def test_agent_conversational_reply_resolution():
    with tempfile.TemporaryDirectory() as scripts_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        agent = KrokBotAgent(script_manager=mgr)
        agent._generate_script = lambda fn, tp, sp: "print('Audit sweep completed')\n"

        # Initial prompt asks confirmation
        res1 = agent.run_task("create python script audit_sweep.py")
        assert res1["status"] == "ask_confirmation"

        # User replies "save it" in next turn
        res2 = agent.run_task("save it")
        assert res2["status"] == "success"
        assert res2["save_mode"] == "saved"
        assert mgr.get_script("audit_sweep.py") is not None

def test_dashboard_and_bridge_script_apis():
    client_dash = TestClient(dashboard_app)
    client_bridge = TestClient(bridge_app)

    # 1. Create script via dashboard
    create_payload = {
        "name": "api_test_script.py",
        "code": "print('Bridge and dashboard API test')\n",
        "purpose": "REST API unit test script",
        "category": "API Verification"
    }
    dash_post = client_dash.post("/api/scripts", json=create_payload)
    assert dash_post.status_code == 200
    assert dash_post.json()["name"] == "api_test_script.py"

    # 2. List via bridge
    bridge_list = client_bridge.get("/api/v1/scripts")
    assert bridge_list.status_code == 200
    names = [s["name"] for s in bridge_list.json()]
    assert "api_test_script.py" in names

    # 3. Get script details via dashboard
    dash_get = client_dash.get("/api/scripts/api_test_script.py")
    assert dash_get.status_code == 200
    assert "Bridge and dashboard API test" in dash_get.json()["code"]

    # 4. Run script via bridge
    bridge_run = client_bridge.post("/api/v1/scripts/api_test_script.py/run")
    assert bridge_run.status_code == 200
    assert bridge_run.json()["exit_code"] == 0

    # 4b. Stream script via dashboard SSE
    dash_stream = client_dash.get("/api/scripts/api_test_script.py/stream")
    assert dash_stream.status_code == 200
    assert "text/event-stream" in dash_stream.headers["content-type"]
    assert "Bridge and dashboard API test" in dash_stream.text
    assert '"event": "complete"' in dash_stream.text

    # 4c. Stream script via bridge SSE
    bridge_stream = client_bridge.get("/api/v1/scripts/api_test_script.py/stream")
    assert bridge_stream.status_code == 200
    assert "text/event-stream" in bridge_stream.headers["content-type"]
    assert '"event": "complete"' in bridge_stream.text

    # 5. Delete via dashboard
    dash_del = client_dash.delete("/api/scripts/api_test_script.py")
    assert dash_del.status_code == 200

    # Verify deleted
    get_after = client_dash.get("/api/scripts/api_test_script.py")
    assert get_after.status_code == 404
