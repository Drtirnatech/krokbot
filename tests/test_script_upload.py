import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from krokbot.scripts.manager import ScriptAssetManager
from krokbot.sandbox.executor import SandboxExecutor
from krokbot.dashboard.server import app as dashboard_app

client = TestClient(dashboard_app)

def test_validate_and_verify_valid_script():
    with tempfile.TemporaryDirectory() as scripts_dir, tempfile.TemporaryDirectory() as sandbox_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        sandbox = SandboxExecutor(workspace_dir=sandbox_dir)

        code = "import sys\nprint('Verification check passed!')\nsys.exit(0)\n"
        res = mgr.validate_and_verify(
            filename="diag_test.py",
            code=code,
            requirements_content=None,
            auto_install=False,
            sandbox_executor=sandbox
        )

        assert res["valid_syntax"] is True
        assert res["requirements_ok"] is True
        assert res["execution_verified"] is True
        assert res["exit_code"] == 0
        assert "Verification check passed!" in res["stdout"]
        assert res["status"] == "verified"

def test_validate_and_verify_syntax_error():
    with tempfile.TemporaryDirectory() as scripts_dir, tempfile.TemporaryDirectory() as sandbox_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        sandbox = SandboxExecutor(workspace_dir=sandbox_dir)

        bad_code = "def broken_func(\nprint('missing paren')\n"
        res = mgr.validate_and_verify(
            filename="broken.py",
            code=bad_code,
            requirements_content=None,
            auto_install=False,
            sandbox_executor=sandbox
        )

        assert res["valid_syntax"] is False
        assert res["status"] == "syntax_error"
        assert "SyntaxError" in res["error"]

def test_validate_and_verify_with_installed_requirements():
    with tempfile.TemporaryDirectory() as scripts_dir, tempfile.TemporaryDirectory() as sandbox_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        sandbox = SandboxExecutor(workspace_dir=sandbox_dir)

        code = "import json\nimport os\nprint('JSON & OS ready')\n"
        reqs = "# Standard dependencies\njson\n"
        res = mgr.validate_and_verify(
            filename="req_check.py",
            code=code,
            requirements_content=reqs,
            auto_install=False,
            sandbox_executor=sandbox
        )

        assert res["valid_syntax"] is True
        assert res["requirements_ok"] is True
        assert res["exit_code"] == 0
        assert res["status"] == "verified"

def test_validate_and_verify_execution_failure():
    with tempfile.TemporaryDirectory() as scripts_dir, tempfile.TemporaryDirectory() as sandbox_dir:
        mgr = ScriptAssetManager(scripts_dir=scripts_dir)
        sandbox = SandboxExecutor(workspace_dir=sandbox_dir)

        failing_code = "import sys\nprint('starting')\nraise RuntimeError('Simulated failure during validation')\n"
        res = mgr.validate_and_verify(
            filename="fail_test.py",
            code=failing_code,
            requirements_content=None,
            auto_install=False,
            sandbox_executor=sandbox
        )

        assert res["valid_syntax"] is True
        assert res["execution_verified"] is False
        assert res["exit_code"] != 0
        assert "RuntimeError" in res["stderr"]
        assert res["status"] == "execution_failed"

def test_api_scripts_upload_endpoint():
    script_code = "print('Hello from uploaded API script!')\n"
    response = client.post(
        "/api/scripts/upload",
        data={
            "filename": "uploaded_tool.py",
            "code": script_code,
            "purpose": "Test API script upload functionality",
            "category": "Testing"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["verified", "success"]
    assert data["name"] == "uploaded_tool.py"
    assert "verification" in data
    assert data["verification"]["exit_code"] == 0

    # Cleanup
    client.delete("/api/scripts/uploaded_tool.py")
