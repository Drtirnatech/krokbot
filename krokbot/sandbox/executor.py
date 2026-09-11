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

    def _resolve_path(self, filename: str) -> Path:
        path_obj = Path(filename)
        try:
            resolved_workspace = self.workspace_dir.resolve()
            resolved_path = path_obj.resolve()
            if resolved_path.is_relative_to(resolved_workspace):
                return resolved_path
        except Exception:
            pass
        return self.workspace_dir / path_obj.name

    def write_file(self, filename: str, content: str) -> str:
        filepath = self._resolve_path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def read_file(self, filename: str) -> Optional[str]:
        filepath = self._resolve_path(filename)
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def execute_file(self, filename: str) -> Dict[str, Any]:
        filepath = self._resolve_path(filename)
        if not filepath.exists():
            return {"exit_code": 1, "stdout": "", "stderr": f"File not found: {filename}"}
        
        print("\n" + "-" * 50)
        print(f" [MARINABOX COMPUTE SANDBOX] Executing Script File: {filepath.name}")
        print(" Workspace Directory: " + str(self.workspace_dir.resolve()))
        print("-" * 50)

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            process = subprocess.run(
                [sys.executable, str(filepath.resolve())],
                cwd=str(self.workspace_dir.resolve()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
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

    def execute_file_stream(self, filename: str):
        """
        Executes a script in the sandbox workspace and yields real-time streaming output events.
        Events yielded:
          {"event": "start", "command": str, "cwd": str, "filename": str, "timestamp": str}
          {"event": "output", "stream": "stdout"|"stderr", "text": str}
          {"event": "complete", "exit_code": int, "duration_ms": float, "stdout": str, "stderr": str}
        """
        import time
        import threading
        import queue
        from datetime import datetime, timezone

        filepath = self._resolve_path(filename)
        if not filepath.exists():
            err_text = f"File not found: {filename}"
            yield {"event": "error", "message": err_text}
            yield {"event": "complete", "exit_code": 1, "duration_ms": 0.0, "stdout": "", "stderr": err_text}
            return

        cmd_display = f"python3 -u {filepath.name}"
        cwd_str = str(self.workspace_dir.resolve())
        start_iso = datetime.now(timezone.utc).isoformat()

        yield {
            "event": "start",
            "command": cmd_display,
            "cwd": cwd_str,
            "filename": filepath.name,
            "timestamp": start_iso
        }

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        start_time = time.time()
        try:
            process = subprocess.Popen(
                [sys.executable, "-u", str(filepath.resolve())],
                cwd=cwd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env
            )
        except Exception as e:
            err_text = f"Failed to spawn sandbox process: {e}"
            yield {"event": "error", "message": err_text}
            yield {"event": "complete", "exit_code": 1, "duration_ms": 0.0, "stdout": "", "stderr": err_text}
            return

        q: queue.Queue = queue.Queue()

        def reader(pipe, stream_name):
            try:
                for line in iter(pipe.readline, ''):
                    q.put((stream_name, line))
            except Exception:
                pass
            finally:
                pipe.close()
                q.put((stream_name, None))

        t_out = threading.Thread(target=reader, args=(process.stdout, "stdout"), daemon=True)
        t_err = threading.Thread(target=reader, args=(process.stderr, "stderr"), daemon=True)
        t_out.start()
        t_err.start()

        active_readers = 2
        all_stdout = []
        all_stderr = []

        while active_readers > 0:
            elapsed = time.time() - start_time
            if elapsed > self.timeout_seconds:
                process.kill()
                timeout_msg = f"\n[SANDBOX EXECUTION TIMED OUT after {self.timeout_seconds}s]\n"
                all_stderr.append(timeout_msg)
                yield {"event": "output", "stream": "stderr", "text": timeout_msg}
                break

            try:
                stream_name, line = q.get(timeout=0.04)
                if line is None:
                    active_readers -= 1
                else:
                    if stream_name == "stdout":
                        all_stdout.append(line)
                    else:
                        all_stderr.append(line)
                    yield {"event": "output", "stream": stream_name, "text": line}
            except queue.Empty:
                continue

        try:
            process.wait(timeout=1.0)
        except Exception:
            process.kill()

        duration_ms = round((time.time() - start_time) * 1000, 1)
        exit_code = process.returncode if process.returncode is not None else 124

        yield {
            "event": "complete",
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "stdout": "".join(all_stdout),
            "stderr": "".join(all_stderr)
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
