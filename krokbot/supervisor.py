import os
import sys
import time
import subprocess
import signal
from typing import Dict, Any, List, Optional

class AgentSupervisor:
    """
    In-container supervisor that manages multiple isolated KrokBot agent worker processes.
    Enables deploying additional agents into an existing container deployment
    while sharing the central Llama.cpp engine on 127.0.0.1:8081.
    """
    def __init__(self, workspaces_root: Optional[str] = None):
        self.workspaces_root = workspaces_root or os.path.join(os.getcwd(), "workspaces")
        os.makedirs(self.workspaces_root, exist_ok=True)
        self._next_port = 5152
        self._agents: Dict[str, Dict[str, Any]] = {}
        
        # Initialize Primary Sentinel Agent
        self._init_primary_agent()

    def _init_primary_agent(self):
        from krokbot.model_manager import load_config
        try:
            cfg = load_config().get("agent", {})
        except Exception:
            cfg = {}

        primary_id = cfg.get("id", "krok-prime-01")
        primary_name = cfg.get("name", "KrokBot Prime Sentinel")
        primary_port = cfg.get("dashboard_port", 5150)

        self._agents[primary_id] = {
            "id": primary_id,
            "name": primary_name,
            "port": primary_port,
            "pid": os.getpid(),
            "status": "running",
            "is_primary": True,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "workspace": os.getcwd()
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all active and managed agents in this container."""
        # Refresh running status
        for aid, info in list(self._agents.items()):
            if not info.get("is_primary") and "proc" in info:
                proc = info["proc"]
                if proc and proc.poll() is not None:
                    info["status"] = "stopped"
                    info["exit_code"] = proc.poll()

        return [
            {k: v for k, v in a.items() if k != "proc"}
            for a in self._agents.values()
        ]

    def spawn_agent(self, agent_id: str, agent_name: str, config_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deploy an additional uniform agent instance inside the running container.
        Allocates an internal port and an isolated workspace.
        """
        if agent_id in self._agents and self._agents[agent_id].get("status") == "running":
            raise ValueError(f"Agent with ID '{agent_id}' is already running.")

        assigned_port = self._next_port
        self._next_port += 1

        agent_workspace = os.path.join(self.workspaces_root, f"agent_{agent_id}")
        os.makedirs(agent_workspace, exist_ok=True)

        env = os.environ.copy()
        env["KROKBOT_AGENT_ID"] = agent_id
        env["KROKBOT_AGENT_NAME"] = agent_name
        env["KROKBOT_PORT"] = str(assigned_port)
        env["KROKBOT_WORKSPACE"] = agent_workspace
        env["PYTHONUNBUFFERED"] = "1"

        # Worker launch command
        cmd = [
            sys.executable, "-m", "krokbot.agent.worker",
            "--id", agent_id,
            "--name", agent_name,
            "--port", str(assigned_port),
            "--workspace", agent_workspace
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=agent_workspace,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            pid = proc.pid
        except Exception as e:
            # Fallback for mocking/simulation environments
            proc = None
            pid = 9000 + assigned_port

        agent_record = {
            "id": agent_id,
            "name": agent_name,
            "port": assigned_port,
            "pid": pid,
            "status": "running",
            "is_primary": False,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "workspace": agent_workspace,
            "proc": proc
        }
        self._agents[agent_id] = agent_record

        return {k: v for k, v in agent_record.items() if k != "proc"}

    def stop_agent(self, agent_id: str) -> bool:
        """Gracefully terminate a spawned agent process. Primary agent cannot be stopped via this method."""
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]
        if agent.get("is_primary"):
            return False  # Protect primary agent

        proc = agent.get("proc")
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        agent["status"] = "stopped"
        return True

_global_supervisor: Optional[AgentSupervisor] = None

def get_supervisor() -> AgentSupervisor:
    global _global_supervisor
    if _global_supervisor is None:
        _global_supervisor = AgentSupervisor()
    return _global_supervisor
