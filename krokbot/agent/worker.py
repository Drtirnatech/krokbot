import argparse
import sys
import os
import uvicorn
from fastapi import FastAPI
from krokbot.agent.core import KrokBotAgent

def create_worker_app(agent_id: str, agent_name: str, port: int, workspace: str) -> FastAPI:
    app = FastAPI(title=f"KrokBot Worker - {agent_name}", version="1.0.0")
    agent = KrokBotAgent(agent_id=agent_id, agent_name=agent_name, port=port, is_primary=False)

    @app.get("/api/agent/info")
    @app.get("/api/health")
    def info():
        return {
            "id": agent_id,
            "name": agent_name,
            "port": port,
            "workspace": workspace,
            "status": "running"
        }

    @app.post("/api/prompt")
    @app.post("/api/chat")
    def prompt_endpoint(payload: dict):
        text = payload.get("prompt", "")
        reply = agent.run(text)
        return {"status": "success", "reply": reply, "response": reply, "agent_id": agent_id}

    return app

def main():
    parser = argparse.ArgumentParser(description="KrokBot Agent Subprocess Worker")
    parser.add_argument("--id", required=True, help="Agent unique ID")
    parser.add_argument("--name", required=True, help="Agent human name")
    parser.add_argument("--port", type=int, required=True, help="Internal port")
    parser.add_argument("--workspace", required=True, help="Workspace path")
    args = parser.parse_args()

    app = create_worker_app(args.id, args.name, args.port, args.workspace)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
