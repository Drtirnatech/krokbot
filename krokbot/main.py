import sys
import threading
import uvicorn
import time
from krokbot.bridge.main import app as bridge_app
from krokbot.dashboard.server import app as dashboard_app, export_health_report
from krokbot.agent.core import KrokBotAgent

def start_server(app, port):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

def main():
    print("=" * 60)
    print("  KrokBot - Autonomous Workstation Health Agent PoC")
    print("=" * 60)

    # 1. Start Host Bridge in background thread (port 8990)
    print("[1/4] Starting Host API Bridge on http://localhost:8990 ...")
    bridge_thread = threading.Thread(target=start_server, args=(bridge_app, 8990), daemon=True)
    bridge_thread.start()

    # 2. Start Web Dashboard in background thread (port 5150)
    print("[2/4] Starting Web Dashboard on http://localhost:5150 ...")
    dash_thread = threading.Thread(target=start_server, args=(dashboard_app, 5150), daemon=True)
    dash_thread.start()

    time.sleep(1.5)

    # 3. Initialize and run KrokBot Agent
    print("[3/4] Running KrokBot Health Diagnostic Task via Local Ollama...")
    agent = KrokBotAgent()
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
