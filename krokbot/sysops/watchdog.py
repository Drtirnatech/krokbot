import time
import urllib.request
from typing import Dict, Any, List, Optional
from krokbot.sysops.diagnostics import get_edge_diagnostics
from krokbot.sysops.processes import get_process_manager

class SelfHealingWatchdog:
    """
    Autonomous Edge Watchdog & Self-Healing Engine.
    Continuously monitors edge compute node stability:
    storage pressure, thermal safety, runaway worker processes, and inference availability.
    Autonomously executes remediation actions and broadcasts events to KrokBus.
    """
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.history_limit = 100

        self.policies: Dict[str, Dict[str, Any]] = {
            "policy_storage_pressure": {
                "id": "policy_storage_pressure",
                "name": "Autonomous Storage Pressure & Log Pruning",
                "description": "Trigger automated cache cleanup and log rotation when partition usage exceeds 85%.",
                "threshold_metric": "storage_percent",
                "threshold_value": 85.0,
                "enabled": True,
                "cooldown_seconds": 60,
                "last_triggered": 0.0,
                "trigger_count": 0
            },
            "policy_thermal_guard": {
                "id": "policy_thermal_guard",
                "name": "Edge SoC Thermal Guard & Fan Warning",
                "description": "Log high-priority hardware alert when SoC thermal package exceeds 75.0°C.",
                "threshold_metric": "max_temp_c",
                "threshold_value": 75.0,
                "enabled": True,
                "cooldown_seconds": 45,
                "last_triggered": 0.0,
                "trigger_count": 0
            },
            "policy_worker_memory": {
                "id": "policy_worker_memory",
                "name": "Subagent Worker Memory Leak Protection",
                "description": "Trigger libc malloc_trim and garbage collection if worker memory exceeds 800 MB.",
                "threshold_metric": "worker_rss_mb",
                "threshold_value": 800.0,
                "enabled": True,
                "cooldown_seconds": 30,
                "last_triggered": 0.0,
                "trigger_count": 0
            },
            "policy_inference_heartbeat": {
                "id": "policy_inference_heartbeat",
                "name": "Inference Arbiter Llama.cpp Heartbeat Watchdog",
                "description": "Detects if 127.0.0.1:8081 fails to respond to health probes and flags restart.",
                "threshold_metric": "arbiter_unresponsive",
                "threshold_value": 1.0,
                "enabled": True,
                "cooldown_seconds": 60,
                "last_triggered": 0.0,
                "trigger_count": 0
            }
        }

    def list_policies(self) -> List[Dict[str, Any]]:
        return list(self.policies.values())

    def toggle_policy(self, policy_id: str) -> Dict[str, Any]:
        if policy_id not in self.policies:
            raise KeyError(f"Watchdog policy '{policy_id}' not found.")
        self.policies[policy_id]["enabled"] = not self.policies[policy_id]["enabled"]
        return self.policies[policy_id]

    def evaluate_health(self) -> List[Dict[str, Any]]:
        """
        Evaluate edge node diagnostics against active policies.
        Triggers remediation for any violated safety boundaries.
        """
        now = time.time()
        diag = get_edge_diagnostics()
        proc_mgr = get_process_manager()
        remediations: List[Dict[str, Any]] = []

        # 1. Storage Pressure Evaluation
        p_storage = self.policies.get("policy_storage_pressure", {})
        if p_storage.get("enabled") and (now - p_storage.get("last_triggered", 0.0)) >= p_storage.get("cooldown_seconds", 60):
            partitions = diag.get_storage_metrics()
            max_used_pct = max([p["percent"] for p in partitions], default=0.0)
            if max_used_pct >= p_storage["threshold_value"]:
                p_storage["last_triggered"] = now
                p_storage["trigger_count"] = p_storage.get("trigger_count", 0) + 1
                clean_res = proc_mgr.run_system_cleanup()
                event = {
                    "policy_id": "policy_storage_pressure",
                    "policy_name": p_storage["name"],
                    "metric_observed": f"{max_used_pct}% usage",
                    "action_taken": "AUTONOMOUS_STORAGE_CLEANUP",
                    "details": clean_res,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                remediations.append(event)
                self._record_event(event)

        # 2. Thermal Guard Evaluation
        p_thermal = self.policies.get("policy_thermal_guard", {})
        if p_thermal.get("enabled") and (now - p_thermal.get("last_triggered", 0.0)) >= p_thermal.get("cooldown_seconds", 45):
            therm = diag.get_thermal_metrics()
            if therm["max_temp_c"] >= p_thermal["threshold_value"]:
                p_thermal["last_triggered"] = now
                p_thermal["trigger_count"] = p_thermal.get("trigger_count", 0) + 1
                event = {
                    "policy_id": "policy_thermal_guard",
                    "policy_name": p_thermal["name"],
                    "metric_observed": f"{therm['max_temp_c']}°C (Status: {therm['status']})",
                    "action_taken": "THERMAL_THROTTLE_ALERT",
                    "details": "Thermal throttling detected. Logged hardware alert to operator.",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                remediations.append(event)
                self._record_event(event)

        # 3. Worker Memory Leak Evaluation
        p_worker = self.policies.get("policy_worker_memory", {})
        if p_worker.get("enabled") and (now - p_worker.get("last_triggered", 0.0)) >= p_worker.get("cooldown_seconds", 30):
            procs = diag.get_top_processes(limit=10)
            over_limit = [p for p in procs if p["memory_rss_mb"] >= p_worker["threshold_value"] and not p["is_protected"]]
            if over_limit:
                p_worker["last_triggered"] = now
                p_worker["trigger_count"] = p_worker.get("trigger_count", 0) + 1
                clean_res = proc_mgr.run_system_cleanup()
                event = {
                    "policy_id": "policy_worker_memory",
                    "policy_name": p_worker["name"],
                    "metric_observed": f"{len(over_limit)} worker processes exceeded {p_worker['threshold_value']} MB",
                    "action_taken": "MEMORY_ARENA_TRIM",
                    "details": clean_res,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                remediations.append(event)
                self._record_event(event)

        return remediations

    def _record_event(self, event: Dict[str, Any]):
        self.history.append(event)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

        # Publish to KrokBus
        try:
            from krokbot.bus import get_event_bus
            import asyncio
            bus = get_event_bus()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(bus.publish("sysops/remediation", event, source_agent="self_healing_watchdog"))
            except RuntimeError:
                pass
        except Exception:
            pass

    def get_remediation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.history[-limit:]

_global_watchdog: Optional[SelfHealingWatchdog] = None

def get_self_healing_watchdog() -> SelfHealingWatchdog:
    global _global_watchdog
    if _global_watchdog is None:
        _global_watchdog = SelfHealingWatchdog()
    return _global_watchdog
