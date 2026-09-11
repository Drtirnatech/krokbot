import sys
import threading
import uvicorn
import time
from krokbot.bridge.main import app as bridge_app, set_scheduler_manager as bridge_set_scheduler_manager
from krokbot.dashboard.server import app as dashboard_app, export_health_report, set_scheduler_manager, set_agent_instance
from krokbot.agent.core import KrokBotAgent
from krokbot.scheduler.manager import CronSchedulerManager

def start_server(app, port):
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

def main():
    print("=" * 60)
    print("  KrokBot - Autonomous Workstation Health Agent PoC")
    print("=" * 60)

    # Initialize Cron Scheduler Manager
    scheduler = CronSchedulerManager()
    scheduler.start()
    set_scheduler_manager(scheduler)
    bridge_set_scheduler_manager(scheduler)

    # 1. Start Host Bridge if running natively on host
    import os
    is_docker = os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER")
    if not is_docker:
        print("[1/4] Starting Native Host API Bridge on http://localhost:8992 ...")
        bridge_thread = threading.Thread(target=start_server, args=(bridge_app, 8992), daemon=True)
        bridge_thread.start()
    else:
        print("[1/4] Containerized environment detected. Host Bridge routes to native host machine.")

    # 2. Start Web Dashboard in background thread (port 5150)
    print("[2/4] Starting Web Dashboard on http://localhost:5150 ...")
    dash_thread = threading.Thread(target=start_server, args=(dashboard_app, 5150), daemon=True)
    dash_thread.start()

    time.sleep(1.5)

    # 3. Initialize and run KrokBot Agent
    print("[3/4] Running KrokBot Health Diagnostic Task via Llama.cpp...")
    agent = KrokBotAgent(scheduler_manager=scheduler, port=5150, is_primary=True)
    set_agent_instance(agent)
    task_prompt = "Check workstation health, OS, storage, and active services, and output diagnostic summary."
    result = agent.run_task(task_prompt)

    # 4. Export Markdown Health Report
    output_path = "krokbot_health_report.md"
    print(f"[4/4] Exporting Health Report to {output_path} ...")
    export_health_report(output_path, result["report"], result["metrics"])

    print("\n" + "=" * 60)
    print("  KrokBot Diagnostic Complete!")
    print(f"  - Web Dashboard: http://localhost:5150")
    print(f"  - Report File:   {output_path}")
    print("  Server is active. Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping KrokBot servers...")

if __name__ == "__main__":
    main()
