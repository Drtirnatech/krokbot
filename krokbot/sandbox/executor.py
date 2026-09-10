import sys
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional

class SandboxExecutor:
    """
    Executes dynamic diagnostic scripts and persistent code in an isolated execution sandbox workspace.
    Uses MarinaBox SDK if available, with a dedicated local workspace directory fallback.
    """
    def __init__(self, timeout_seconds: int = 15, workspace_dir: Optional[str] = None):
        self.timeout_seconds = timeout_seconds
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path("data/sandbox_workspace")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def write_file(self, filename: str, content: str) -> str:
        filepath = self.workspace_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def read_file(self, filename: str) -> Optional[str]:
        filepath = self.workspace_dir / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def execute_file(self, filename: str) -> Dict[str, Any]:
        filepath = self.workspace_dir / filename
        if not filepath.exists():
            return {"exit_code": 1, "stdout": "", "stderr": f"File not found: {filename}"}
        
        print("\n" + "-" * 50)
        print(f" [MARINABOX COMPUTE SANDBOX] Executing Script File: {filename}")
        print(" Workspace Directory: " + str(self.workspace_dir.resolve()))
        print("-" * 50)

        try:
            process = subprocess.run(
                [sys.executable, str(filepath)],
                cwd=str(self.workspace_dir.resolve()),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            print(f" [SANDBOX EXECUTION COMPLETE] Exit Code: {process.returncode}")
            if process.stdout.strip():
                print(f" [SANDBOX STDOUT]:\n{process.stdout.strip()}")
            if process.stderr.strip():
                print(f" [SANDBOX STDERR]:\n{process.stderr.strip()}")
            print("-" * 50 + "\n")
            return {
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr
            }
        except subprocess.TimeoutExpired:
            print(f" [SANDBOX EXECUTION TIMED OUT after {self.timeout_seconds}s]")
            print("-" * 50 + "\n")
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds"
            }

    def execute_script(self, code: str, language: str = "python", filename: Optional[str] = None) -> Dict[str, Any]:
        if language.lower() != "python":
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Unsupported language: {language}"
            }

        script_name = filename or "temp_script.py"
        self.write_file(script_name, code)
        return self.execute_file(script_name)
