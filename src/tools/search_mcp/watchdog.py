# src/tools/search_mcp/watchdog.py
import time
import os
import sys
import subprocess
from pathlib import Path

ACTIVITY_FILE = Path("/tmp/mcp_last_activity")

class WatchdogState:
    def __init__(self, timeout_seconds: int = 180, activity_file: Path = ACTIVITY_FILE):
        self.timeout_seconds = timeout_seconds
        self.activity_file = Path(activity_file)

    def touch(self) -> None:
        try:
            self.activity_file.parent.mkdir(parents=True, exist_ok=True)
            self.activity_file.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass

    def get_last_activity(self) -> float:
        if not self.activity_file.exists():
            return time.time()
        try:
            return float(self.activity_file.read_text(encoding="utf-8").strip())
        except Exception:
            return time.time()

    def is_expired(self) -> bool:
        elapsed = time.time() - self.get_last_activity()
        return elapsed >= self.timeout_seconds

def run_watchdog_daemon(timeout_seconds: int = 180):
    watchdog = WatchdogState(timeout_seconds=timeout_seconds)
    watchdog.touch()
    print(f"[Watchdog] Active. Monitoring container idle timeout ({timeout_seconds}s)...", flush=True)

    while True:
        time.sleep(15)
        if watchdog.is_expired():
            print(f"[Watchdog] Inactivity threshold ({timeout_seconds}s) reached. Initiating container shutdown...", flush=True)
            # Signal supervisord to shut down cleanly
            try:
                subprocess.run(["supervisorctl", "shutdown"], timeout=5)
            except Exception:
                pass
            sys.exit(0)

if __name__ == "__main__":
    run_watchdog_daemon(180)
