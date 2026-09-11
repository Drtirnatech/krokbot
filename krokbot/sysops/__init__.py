"""
KrokBot Edge Compute SysOps & Diagnostics Subsystem.
Provides hardware thermal monitoring, process inspection,
safe task termination, and autonomous self-healing watchdogs for edge nodes.
"""
from krokbot.sysops.diagnostics import get_edge_diagnostics, EdgeDiagnostics
from krokbot.sysops.processes import get_process_manager, ProcessManager
from krokbot.sysops.watchdog import get_self_healing_watchdog, SelfHealingWatchdog

__all__ = [
    "get_edge_diagnostics",
    "EdgeDiagnostics",
    "get_process_manager",
    "ProcessManager",
    "get_self_healing_watchdog",
    "SelfHealingWatchdog"
]
