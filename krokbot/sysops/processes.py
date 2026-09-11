import os
import time
import signal
import psutil
import gc
from typing import Dict, Any, List, Optional

class ProcessManager:
    """
    Safely inspects, manages, and terminates edge node processes with strict safety interlocks.
    Also provides operational memory trimming and temporary cache cleanup.
    """
    def __init__(self):
        self.protected_pids = {1, os.getpid()}

    def is_pid_protected(self, pid: int) -> bool:
        if pid in self.protected_pids:
            return True
        try:
            p = psutil.Process(pid)
            # Protect system init, container shell entry, and primary dashboard
            if p.name().lower() in ["systemd", "init", "tini", "docker-init", "krokbot_agent"]:
                return True
        except Exception:
            pass
        return False

    def list_processes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List running processes with resource utilization metrics."""
        results = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status']):
            try:
                mem = p.info.get('memory_info')
                rss_mb = round(mem.rss / (1024 * 1024), 1) if mem else 0.0
                pid = p.info['pid']
                name = p.info.get('name') or 'unknown'

                results.append({
                    "pid": pid,
                    "name": name,
                    "cmd": name,
                    "status": p.info.get('status') or 'running',
                    "cpu_percent": round(p.info.get('cpu_percent') or 0.0, 1),
                    "memory_rss_mb": rss_mb,
                    "is_protected": self.is_pid_protected(pid)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue

        return sorted(results, key=lambda x: x["memory_rss_mb"], reverse=True)[:limit]

    def terminate_process(self, pid: int, force: bool = False) -> Dict[str, Any]:
        """
        Safely terminate or kill a process if not on the protected blacklist.
        """
        if self.is_pid_protected(pid):
            raise PermissionError(f"PID {pid} is protected by edge safety policy and cannot be terminated.")

        try:
            p = psutil.Process(pid)
            proc_name = p.name()
            if force:
                p.kill()
                action = "KILL (SIGKILL)"
            else:
                p.terminate()
                action = "TERMINATE (SIGTERM)"

            return {
                "status": "success",
                "pid": pid,
                "name": proc_name,
                "action": action,
                "message": f"Successfully sent {action} to process {pid} ({proc_name})."
            }
        except psutil.NoSuchProcess:
            raise LookupError(f"Process with PID {pid} was not found or has already terminated.")
        except psutil.AccessDenied:
            raise PermissionError(f"Access denied terminating PID {pid}.")

    def run_system_cleanup(self) -> Dict[str, Any]:
        """
        Trigger Python GC, glibc memory trimming, and prune temporary sandbox files.
        """
        before_mem = psutil.virtual_memory().used
        
        # 1. Collect Python garbage
        collected = gc.collect()

        # 2. Trim libc memory arenas back to kernel
        trimmed = False
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            if hasattr(libc, "malloc_trim"):
                libc.malloc_trim(0)
                trimmed = True
        except Exception:
            pass

        # 3. Prune temporary sandbox workspace files if directory exists
        cleaned_files = 0
        cleaned_bytes = 0
        sandbox_dir = os.path.join(os.getcwd(), "data", "sandbox_workspace")
        if os.path.isdir(sandbox_dir):
            try:
                for f in os.listdir(sandbox_dir):
                    if f.startswith("tmp_") or f.endswith(".tmp"):
                        fpath = os.path.join(sandbox_dir, f)
                        try:
                            fsize = os.path.getsize(fpath)
                            os.remove(fpath)
                            cleaned_files += 1
                            cleaned_bytes += fsize
                        except Exception:
                            pass
            except Exception:
                pass

        after_mem = psutil.virtual_memory().used
        recovered_mb = max(0.0, round((before_mem - after_mem) / (1024 * 1024), 2))

        return {
            "status": "success",
            "gc_objects_collected": collected,
            "malloc_trimmed": trimmed,
            "temp_files_pruned": cleaned_files,
            "cleaned_bytes": cleaned_bytes,
            "memory_recovered_mb": recovered_mb,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

_global_process_manager: Optional[ProcessManager] = None

def get_process_manager() -> ProcessManager:
    global _global_process_manager
    if _global_process_manager is None:
        _global_process_manager = ProcessManager()
    return _global_process_manager
