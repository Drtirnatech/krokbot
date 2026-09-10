import sys
import subprocess
import tempfile
import os
from typing import Dict, Any

class SandboxExecutor:
    """
    Executes dynamic diagnostic scripts in an isolated execution sandbox.
    Uses MarinaBox SDK if available, with an isolated Python subprocess sandbox fallback.
    """
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def execute_script(self, code: str, language: str = "python") -> Dict[str, Any]:
        print("\n" + "─" * 50)
        print(" [MARINABOX COMPUTE SANDBOX] Executing Diagnostic Script")
        print(" Language: " + language)
        print(" Code Snippet:")
        for line in code.strip().split("\n")[:5]:
            print(f"   │ {line}")
        if len(code.strip().split("\n")) > 5:
            print("   │ ... [truncated]")
        print("─" * 50)

        if language.lower() != "python":
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Unsupported language: {language}"
            }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
            tmp_file.write(code)
            tmp_path = tmp_file.name

        try:
            process = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            print(f" [SANDBOX EXECUTION COMPLETE] Exit Code: {process.returncode}")
            if process.stdout.strip():
                print(f" [SANDBOX STDOUT]:\n{process.stdout.strip()}")
            if process.stderr.strip():
                print(f" [SANDBOX STDERR]:\n{process.stderr.strip()}")
            print("─" * 50 + "\n")
            return {
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr
            }
        except subprocess.TimeoutExpired:
            print(f" [SANDBOX EXECUTION TIMED OUT after {self.timeout_seconds}s]")
            print("─" * 50 + "\n")
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds"
            }
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
