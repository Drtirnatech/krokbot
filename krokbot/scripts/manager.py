import os
import re
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

class ScriptAssetManager:
    """
    Manages persistent script assets filed in data/scripts/.
    Every saved script consists of a paired Python file (.py) and Markdown documentation file (.md).
    Supports listing, inspecting, executing, and deleting script assets locally and via remote C2 APIs.
    """
    def __init__(self, scripts_dir: Optional[str] = None):
        if scripts_dir:
            self.scripts_dir = Path(scripts_dir)
        else:
            self.scripts_dir = Path("data/scripts")
        self._lock = threading.RLock()
        self._ensure_dir_exists()

    def _ensure_dir_exists(self) -> None:
        with self._lock:
            self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, filename: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", filename).strip()
        if not clean.endswith(".py"):
            clean += ".py"
        return clean

    def _compute_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _generate_default_markdown(
        self,
        name: str,
        purpose: str,
        code: str,
        category: str = "General Automation",
        author: str = "krokbot_agent",
        requirements_content: Optional[str] = None,
        verification_info: Optional[Dict[str, Any]] = None
    ) -> str:
        sha256 = self._compute_sha256(code)
        now_iso = datetime.now(timezone.utc).isoformat()

        req_section = ""
        if requirements_content and requirements_content.strip():
            req_section = f"""
## Dependencies & Package Requirements (`requirements.txt`)
```text
{requirements_content.strip()}
```
"""

        verification_section = ""
        if verification_info:
            v_exit = verification_info.get("exit_code", 0)
            v_badge = "✓ VERIFIED (Exit Code 0)" if v_exit == 0 else f"⚠ FAILED (Exit Code {v_exit})"
            verification_section = f"""
## Verification & Validation Status
- Status: `{v_badge}`
- Syntax Validation: `{"PASSED" if verification_info.get("valid_syntax", True) else "FAILED"}`
- Requirements Satisfied: `{"YES" if verification_info.get("requirements_ok", True) else "NO"}`
- Execution Latency: `{verification_info.get("duration_ms", 0)} ms`
- Verified At: `{now_iso}`
"""
        
        return f"""# Script Asset: {name}

**Asset Name**: `{name}`  
**Category**: `{category}`  
**Author**: `{author}`  
**Created**: `{now_iso}`  
**Last Modified**: `{now_iso}`  
**SHA-256**: `{sha256}`  
{f"**Status**: `✓ VERIFIED`" if verification_info and verification_info.get("exit_code") == 0 else ""}

---

## Purpose & Functional Summary
{purpose.strip()}
{req_section}
## Execution Requirements
- Runtime: Python 3.10+ in container sandbox compute environment
- Privileges: Sandbox Compute Workspace (`/app/data/sandbox_workspace`)
- External Network: Permitted if Browser/HTTP tools are enabled
{verification_section}
## Inputs & Arguments
- Self-contained execution script. Does not require command-line arguments.

## Outputs & Artifacts
- Standard Output: Live telemetry and status streamed to console
- Workspace Files: May output `./report.txt` or data logs upon completion

## Security & Integrity
- SHA-256 Hash: `{sha256}`
- Policy Status: Governed by KrokBot Agent Tools Security Matrix
"""

    def _parse_markdown_metadata(self, md_path: Path) -> Dict[str, Any]:
        meta = {
            "purpose_summary": "No description provided.",
            "category": "General Automation",
            "author": "krokbot_agent",
            "created_at": None,
            "sha256": None,
            "is_verified": False
        }
        if not md_path.exists():
            return meta

        try:
            content = md_path.read_text(encoding="utf-8")
            
            cat_match = re.search(r"\*\*Category\*\*:\s*`?([^`\n\r]+)`?", content)
            if cat_match:
                meta["category"] = cat_match.group(1).strip()

            author_match = re.search(r"\*\*Author\*\*:\s*`?([^`\n\r]+)`?", content)
            if author_match:
                meta["author"] = author_match.group(1).strip()

            sha_match = re.search(r"\*\*SHA-256\*\*:\s*`?([a-fA-F0-9]{64})`?", content)
            if sha_match:
                meta["sha256"] = sha_match.group(1).strip()

            created_match = re.search(r"\*\*Created\*\*:\s*`?([^`\n\r]+)`?", content)
            if created_match:
                meta["created_at"] = created_match.group(1).strip()

            if "✓ VERIFIED" in content:
                meta["is_verified"] = True

            purpose_match = re.search(r"## Purpose & Functional Summary\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
            if purpose_match:
                summary = purpose_match.group(1).strip()
                if summary:
                    meta["purpose_summary"] = summary
        except Exception:
            pass

        return meta

    def list_scripts(self) -> List[Dict[str, Any]]:
        """List all saved script assets with extracted metadata and purpose summaries."""
        self._ensure_dir_exists()
        scripts = []

        with self._lock:
            for py_file in self.scripts_dir.glob("*.py"):
                name = py_file.name
                base_stem = py_file.stem
                md_file = py_file.with_suffix(".md")
                
                try:
                    stats = py_file.stat()
                    size_bytes = stats.st_size
                    mtime = datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat()
                except Exception:
                    size_bytes = 0
                    mtime = datetime.now(timezone.utc).isoformat()

                has_markup = md_file.exists()
                md_meta = self._parse_markdown_metadata(md_file) if has_markup else {}
                req_file = py_file.with_suffix(".requirements.txt")

                scripts.append({
                    "id": base_stem,
                    "name": name,
                    "filename": name,
                    "markup_filename": f"{base_stem}.md",
                    "size_bytes": size_bytes,
                    "size_formatted": f"{round(size_bytes / 1024, 1)} KB" if size_bytes >= 1024 else f"{size_bytes} B",
                    "modified_at": mtime,
                    "has_markup": has_markup,
                    "has_requirements": req_file.exists(),
                    "is_verified": md_meta.get("is_verified", False),
                    "purpose_summary": md_meta.get("purpose_summary", "No description provided."),
                    "category": md_meta.get("category", "Automation"),
                    "author": md_meta.get("author", "krokbot_agent"),
                    "sha256": md_meta.get("sha256", None)
                })

        # Sort by modified time descending (newest first)
        scripts.sort(key=lambda s: s.get("modified_at") or "", reverse=True)
        return scripts

    def get_script(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve script code, paired markdown documentation, and metadata."""
        clean_name = self._sanitize_name(name)
        py_path = self.scripts_dir / clean_name
        md_path = py_path.with_suffix(".md")
        req_path = py_path.with_suffix(".requirements.txt")

        with self._lock:
            if not py_path.exists():
                return None

            try:
                code = py_path.read_text(encoding="utf-8")
            except Exception as e:
                code = f"# Error reading script: {e}"

            markdown_content = ""
            if md_path.exists():
                try:
                    markdown_content = md_path.read_text(encoding="utf-8")
                except Exception:
                    markdown_content = ""

            requirements_content = ""
            if req_path.exists():
                try:
                    requirements_content = req_path.read_text(encoding="utf-8")
                except Exception:
                    requirements_content = ""

            md_meta = self._parse_markdown_metadata(md_path)
            stats = py_path.stat()

            return {
                "id": py_path.stem,
                "name": clean_name,
                "filename": clean_name,
                "markup_filename": f"{py_path.stem}.md",
                "code": code,
                "markdown": markdown_content,
                "requirements": requirements_content,
                "has_requirements": req_path.exists(),
                "is_verified": md_meta.get("is_verified", False),
                "sha256": self._compute_sha256(code),
                "size_bytes": stats.st_size,
                "modified_at": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
                "has_markup": md_path.exists(),
                "metadata": md_meta,
                "purpose_summary": md_meta.get("purpose_summary", "")
            }

    def save_script(
        self,
        name: str,
        code: str,
        purpose: Optional[str] = None,
        markdown_content: Optional[str] = None,
        category: str = "General Automation",
        author: str = "krokbot_agent",
        requirements_content: Optional[str] = None,
        verification_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Save Python script code and its paired Markdown documentation file."""
        self._ensure_dir_exists()
        clean_name = self._sanitize_name(name)
        py_path = self.scripts_dir / clean_name
        md_path = py_path.with_suffix(".md")
        req_path = py_path.with_suffix(".requirements.txt")

        if not purpose:
            purpose = f"Automated Python task script for {clean_name} synthesized by KrokBot Agent."

        if not markdown_content:
            markdown_content = self._generate_default_markdown(
                name=clean_name,
                purpose=purpose,
                code=code,
                category=category,
                author=author,
                requirements_content=requirements_content,
                verification_info=verification_info
            )

        with self._lock:
            # Write .py file
            py_path.write_text(code, encoding="utf-8")
            # Write paired .md file
            md_path.write_text(markdown_content, encoding="utf-8")
            # Write optional requirements.txt if present
            if requirements_content and requirements_content.strip():
                req_path.write_text(requirements_content.strip() + "\n", encoding="utf-8")

            stats = py_path.stat()
            mtime = datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat()
            sha256 = self._compute_sha256(code)

            return {
                "status": "success",
                "id": py_path.stem,
                "name": clean_name,
                "filename": clean_name,
                "markup_filename": f"{py_path.stem}.md",
                "code": code,
                "markdown": markdown_content,
                "requirements": requirements_content or "",
                "has_requirements": req_path.exists(),
                "is_verified": verification_info.get("exit_code") == 0 if verification_info else False,
                "sha256": sha256,
                "size_bytes": stats.st_size,
                "modified_at": mtime,
                "purpose_summary": purpose
            }

    def delete_script(self, name: str) -> bool:
        """Delete script file (.py) and its paired documentation (.md) and requirements."""
        clean_name = self._sanitize_name(name)
        py_path = self.scripts_dir / clean_name
        md_path = py_path.with_suffix(".md")
        req_path = py_path.with_suffix(".requirements.txt")

        with self._lock:
            deleted = False
            if py_path.exists():
                try:
                    py_path.unlink()
                    deleted = True
                except Exception:
                    pass
            if md_path.exists():
                try:
                    md_path.unlink()
                    deleted = True
                except Exception:
                    pass
            if req_path.exists():
                try:
                    req_path.unlink()
                except Exception:
                    pass
            return deleted

    def validate_and_verify(
        self,
        filename: str,
        code: str,
        requirements_content: Optional[str] = None,
        auto_install: bool = True,
        sandbox_executor = None
    ) -> Dict[str, Any]:
        """
        Validates Python syntax and verifies that execution in the sandbox succeeds,
        checking that all specified requirements in requirements.txt are installed.
        """
        import ast
        import sys
        import subprocess
        import importlib.util

        clean_name = self._sanitize_name(filename)

        # 1. Syntax Check via AST
        try:
            ast.parse(code, filename=clean_name)
            valid_syntax = True
        except SyntaxError as e:
            return {
                "status": "syntax_error",
                "valid_syntax": False,
                "requirements_ok": False,
                "execution_verified": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}",
                "error": f"SyntaxError at line {e.lineno}: {e.msg}",
                "missing_packages": [],
                "installed_packages": [],
                "duration_ms": 0.0
            }

        # 2. Requirements & Dependencies Check
        requirements_ok = True
        missing_packages = []
        installed_packages = []
        install_logs = []

        if requirements_content:
            req_lines = [line.strip() for line in requirements_content.splitlines() if line.strip() and not line.strip().startswith("#")]
            for req_line in req_lines:
                clean_pkg = re.split(r"[><=~!;@\s]", req_line)[0].strip()
                if not clean_pkg:
                    continue

                clean_mod = clean_pkg.replace("-", "_").lower()
                is_installed = False

                if clean_mod in sys.builtin_module_names:
                    is_installed = True
                elif importlib.util.find_spec(clean_mod) is not None:
                    is_installed = True
                else:
                    try:
                        import importlib.metadata
                        importlib.metadata.version(clean_pkg)
                        is_installed = True
                    except Exception:
                        is_installed = False

                if is_installed:
                    installed_packages.append(clean_pkg)
                else:
                    if auto_install:
                        try:
                            p = subprocess.run(
                                [sys.executable, "-m", "pip", "install", req_line],
                                capture_output=True,
                                text=True,
                                timeout=90
                            )
                            if p.returncode == 0:
                                installed_packages.append(clean_pkg)
                                install_logs.append(f"Successfully installed {req_line}")
                            else:
                                missing_packages.append(req_line)
                                requirements_ok = False
                                install_logs.append(f"Failed to install {req_line}: {p.stderr}")
                        except Exception as e:
                            missing_packages.append(req_line)
                            requirements_ok = False
                            install_logs.append(f"Error running pip install {req_line}: {e}")
                    else:
                        missing_packages.append(req_line)
                        requirements_ok = False

        if not requirements_ok:
            return {
                "status": "requirements_missing",
                "valid_syntax": True,
                "requirements_ok": False,
                "execution_verified": False,
                "exit_code": 1,
                "stdout": "\n".join(install_logs),
                "stderr": f"Missing or uninstalled requirements: {', '.join(missing_packages)}",
                "error": f"Missing requirements: {', '.join(missing_packages)}",
                "missing_packages": missing_packages,
                "installed_packages": installed_packages,
                "duration_ms": 0.0
            }

        # 3. Test execution in Sandbox
        if sandbox_executor is None:
            from krokbot.sandbox.executor import SandboxExecutor
            sandbox_executor = SandboxExecutor()

        test_file_name = f"__test_verify_{clean_name}"
        sandbox_executor.write_file(test_file_name, code)

        start_t = datetime.now(timezone.utc)
        exec_res = sandbox_executor.execute_file(test_file_name)
        duration_ms = round((datetime.now(timezone.utc) - start_t).total_seconds() * 1000, 1)

        try:
            test_path = sandbox_executor._resolve_path(test_file_name)
            if test_path.exists():
                test_path.unlink()
        except Exception:
            pass

        exit_code = exec_res.get("exit_code", 1)
        is_verified = (exit_code == 0)

        return {
            "status": "verified" if is_verified else "execution_failed",
            "valid_syntax": True,
            "requirements_ok": True,
            "execution_verified": is_verified,
            "exit_code": exit_code,
            "stdout": exec_res.get("stdout", ""),
            "stderr": exec_res.get("stderr", ""),
            "error": "" if is_verified else f"Execution failed with exit code {exit_code}",
            "missing_packages": missing_packages,
            "installed_packages": installed_packages,
            "install_logs": "\n".join(install_logs),
            "duration_ms": duration_ms
        }

        with self._lock:
            deleted = False
            if py_path.exists():
                try:
                    py_path.unlink()
                    deleted = True
                except Exception:
                    pass
            if md_path.exists():
                try:
                    md_path.unlink()
                    deleted = True
                except Exception:
                    pass
            return deleted

    def run_script(self, name: str, sandbox_executor) -> Dict[str, Any]:
        """Execute a saved script asset inside the container sandbox compute workspace."""
        clean_name = self._sanitize_name(name)
        script_info = self.get_script(clean_name)
        if not script_info:
            return {
                "exit_code": 404,
                "stdout": "",
                "stderr": f"Script asset '{clean_name}' not found in {self.scripts_dir}."
            }

        code = script_info["code"]
        # Copy / write script to sandbox workspace
        sandbox_executor.write_file(clean_name, code)
        
        start_time = datetime.now(timezone.utc)
        result = sandbox_executor.execute_file(clean_name)
        end_time = datetime.now(timezone.utc)
        duration_ms = round((end_time - start_time).total_seconds() * 1000, 1)

        result["duration_ms"] = duration_ms
        result["script_name"] = clean_name
        result["sha256"] = script_info.get("sha256")
        return result

    def run_script_stream(self, name: str, sandbox_executor):
        """
        Stream real-time terminal execution events for a saved script asset.
        Yields structured event dicts.
        """
        clean_name = self._sanitize_name(name)
        script_info = self.get_script(clean_name)
        if not script_info:
            err_msg = f"Script asset '{clean_name}' not found in {self.scripts_dir}."
            yield {
                "event": "error",
                "message": err_msg
            }
            yield {
                "event": "complete",
                "exit_code": 404,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": err_msg,
                "script_name": clean_name
            }
            return

        code = script_info["code"]
        sandbox_executor.write_file(clean_name, code)
        sha256 = script_info.get("sha256")

        yield {
            "event": "init",
            "script_name": clean_name,
            "sha256": sha256,
            "category": script_info.get("category", "General"),
            "purpose": script_info.get("purpose_summary", "")
        }

        if hasattr(sandbox_executor, "execute_file_stream"):
            for ev in sandbox_executor.execute_file_stream(clean_name):
                ev["script_name"] = clean_name
                if ev.get("event") == "complete":
                    ev["sha256"] = sha256
                yield ev
        else:
            # Fallback for mock or basic executor
            res = sandbox_executor.execute_file(clean_name)
            if res.get("stdout"):
                yield {"event": "output", "stream": "stdout", "text": res["stdout"], "script_name": clean_name}
            if res.get("stderr"):
                yield {"event": "output", "stream": "stderr", "text": res["stderr"], "script_name": clean_name}
            yield {
                "event": "complete",
                "exit_code": res.get("exit_code", 0),
                "duration_ms": 0.0,
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "sha256": sha256,
                "script_name": clean_name
            }

_global_script_manager: Optional[ScriptAssetManager] = None

def get_script_manager(scripts_dir: Optional[str] = None) -> ScriptAssetManager:
    global _global_script_manager
    if _global_script_manager is None or scripts_dir is not None:
        _global_script_manager = ScriptAssetManager(scripts_dir=scripts_dir)
    return _global_script_manager
