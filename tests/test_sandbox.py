import pytest
from krokbot.sandbox.executor import SandboxExecutor

def test_execute_python_script_success(tmp_path):
    executor = SandboxExecutor(workspace_dir=str(tmp_path))
    code = "print('Hello from KrokBot Sandbox')"
    result = executor.execute_script(code, language="python")
    assert result["exit_code"] == 0
    assert "Hello from KrokBot Sandbox" in result["stdout"]
    assert result["stderr"] == ""

def test_execute_python_script_failure(tmp_path):
    executor = SandboxExecutor(workspace_dir=str(tmp_path))
    code = "raise ValueError('Custom sandbox error')"
    result = executor.execute_script(code, language="python")
    assert result["exit_code"] != 0
    assert "ValueError: Custom sandbox error" in result["stderr"]

def test_sandbox_executor_workspace_files(tmp_path):
    executor = SandboxExecutor(workspace_dir=str(tmp_path))
    
    # Write script file
    executor.write_file("test_script.py", "import sys\nwith open('out.txt', 'w') as f: f.write('sandbox output')\nprint('script ran')\n")
    assert (tmp_path / "test_script.py").exists()
    
    # Execute file
    res = executor.execute_file("test_script.py")
    assert res["exit_code"] == 0
    assert "script ran" in res["stdout"]
    
    # Read generated artifact
    out_content = executor.read_file("out.txt")
    assert out_content == "sandbox output"
