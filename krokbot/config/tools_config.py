import os
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_TOOLS_CONFIG: Dict[str, Any] = {
    "version": "1.0",
    "updated_at": "2026-09-11T13:00:00Z",
    "updated_by": "system_default",
    "tools": {
        "python_scripting": {
            "id": "python_scripting",
            "name": "Python Scripting",
            "category": "Code Execution",
            "description": "Allows the agent to generate, synthesize, and execute self-contained Python scripts in the container sandbox workspace.",
            "enabled": True,
            "danger_level": "medium",
            "governance_scope": "container_sandbox",
            "icon": "code"
        },
        "browser_function": {
            "id": "browser_function",
            "name": "Browser Function",
            "category": "Web & Network",
            "description": "Enables web browsing, HTTP fetching, online weather queries, and external webpage content retrieval via the browser automation engine.",
            "enabled": True,
            "danger_level": "low",
            "governance_scope": "external_network",
            "icon": "globe"
        },
        "os_bridge": {
            "id": "os_bridge",
            "name": "OS Bridge (Host Hardware)",
            "category": "Host Hardware Telemetry",
            "description": "Permits reaching the underlying host hardware metrics outside the container (host CPU, RAM, storage partitions, drive telemetry, services list via Host Bridge).",
            "enabled": True,
            "danger_level": "medium",
            "governance_scope": "host_hardware_bridge",
            "icon": "cpu"
        },
        "sandbox_cli": {
            "id": "sandbox_cli",
            "name": "Sandbox CLI",
            "category": "Container Compute",
            "description": "Allows executing shell commands, file manipulations, and terminal subprocesses inside the isolated container sandbox workspace.",
            "enabled": True,
            "danger_level": "medium",
            "governance_scope": "container_sandbox",
            "icon": "terminal"
        },
        "system_cli": {
            "id": "system_cli",
            "name": "System CLI Functions (Host OS)",
            "category": "Host OS Execution",
            "description": "Permits executing underlying operating system command-line commands directly on the host machine hosting the Docker container.",
            "enabled": False,
            "danger_level": "high",
            "governance_scope": "host_os_system",
            "icon": "shield"
        }
    }
}

class AgentToolsManager:
    """
    Manages persistent agent tool enablement policies.
    Persists to data/config/agent_tools.json with thread-safe file I/O.
    Provides APIs for local dashboard UI and remote central C2 orchestration.
    """
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path("data/config/agent_tools.json")
        self._lock = threading.RLock()
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        with self._lock:
            if not self.config_path.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_file_unlocked(DEFAULT_TOOLS_CONFIG)

    def _write_file_unlocked(self, data: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.config_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.config_path)

    def load_config(self) -> Dict[str, Any]:
        with self._lock:
            if not self.config_path.exists():
                self._write_file_unlocked(DEFAULT_TOOLS_CONFIG)
                return json.loads(json.dumps(DEFAULT_TOOLS_CONFIG))
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Ensure all default tools exist in config
                modified = False
                if "tools" not in data:
                    data["tools"] = {}
                    modified = True
                for tool_id, default_item in DEFAULT_TOOLS_CONFIG["tools"].items():
                    if tool_id not in data["tools"]:
                        data["tools"][tool_id] = default_item
                        modified = True
                if modified:
                    self._write_file_unlocked(data)
                return data
            except Exception as e:
                # If corrupted, fallback safely
                print(f"[AgentToolsManager] Error loading {self.config_path}: {e}. Returning defaults.")
                return json.loads(json.dumps(DEFAULT_TOOLS_CONFIG))

    def get_tools(self) -> Dict[str, Any]:
        config = self.load_config()
        return config.get("tools", {})

    def is_tool_enabled(self, tool_id: str) -> bool:
        tools = self.get_tools()
        if tool_id in tools:
            return bool(tools[tool_id].get("enabled", False))
        return False

    def set_tool_enabled(self, tool_id: str, enabled: bool, updated_by: str = "local_dashboard") -> Dict[str, Any]:
        with self._lock:
            config = self.load_config()
            if "tools" not in config:
                config["tools"] = {}
            if tool_id not in config["tools"]:
                if tool_id in DEFAULT_TOOLS_CONFIG["tools"]:
                    config["tools"][tool_id] = DEFAULT_TOOLS_CONFIG["tools"][tool_id].copy()
                else:
                    raise KeyError(f"Unknown tool ID: '{tool_id}'")
            
            config["tools"][tool_id]["enabled"] = bool(enabled)
            config["updated_at"] = datetime.now(timezone.utc).isoformat()
            config["updated_by"] = updated_by
            self._write_file_unlocked(config)
            return config

    def update_tools_policy(self, payload: Dict[str, Any], updated_by: str = "central_c2_api") -> Dict[str, Any]:
        with self._lock:
            config = self.load_config()
            incoming_tools = payload.get("tools", payload)
            
            for tool_id, updates in incoming_tools.items():
                if tool_id in config.get("tools", {}):
                    if isinstance(updates, dict):
                        if "enabled" in updates:
                            config["tools"][tool_id]["enabled"] = bool(updates["enabled"])
                    elif isinstance(updates, bool):
                        config["tools"][tool_id]["enabled"] = updates

            config["updated_at"] = datetime.now(timezone.utc).isoformat()
            config["updated_by"] = updated_by
            self._write_file_unlocked(config)
            return config

    def reset_to_defaults(self, updated_by: str = "admin_reset") -> Dict[str, Any]:
        with self._lock:
            config = json.loads(json.dumps(DEFAULT_TOOLS_CONFIG))
            config["updated_at"] = datetime.now(timezone.utc).isoformat()
            config["updated_by"] = updated_by
            self._write_file_unlocked(config)
            return config

_global_tools_manager: Optional[AgentToolsManager] = None

def get_tools_manager(config_path: Optional[str] = None) -> AgentToolsManager:
    global _global_tools_manager
    if _global_tools_manager is None or config_path is not None:
        _global_tools_manager = AgentToolsManager(config_path=config_path)
    return _global_tools_manager
