import pytest
from krokbot.sandbox.executor import SandboxExecutor

def test_execute_python_script_success():
    executor = SandboxExecutor()
    code = "print('Hello from KrokBot Sandbox')"
    result = executor.execute_script(code, language="python")
    assert result["exit_code"] == 0
    assert "Hello from KrokBot Sandbox" in result["stdout"]
    assert result["stderr"] == ""

def test_execute_python_script_failure():
    executor = SandboxExecutor()
    code = "raise ValueError('Custom sandbox error')"
    result = executor.execute_script(code, language="python")
    assert result["exit_code"] != 0
    assert "ValueError: Custom sandbox error" in result["stderr"]
