# KrokBot - Autonomous Workstation Health Agent PoC

KrokBot is a single-agent proof-of-concept inspired by GrokBot. It utilizes a **MarinaBox** virtual compute sandbox, a local **Llama.cpp** LLM server (running GGUF quantized models), a **Host API Bridge** daemon (`psutil`), and a **Web Dashboard** to inspect system health autonomously.

## Architecture & Features

* **Host API Bridge (`http://localhost:8990`)**: FastAPI daemon providing secure access to host OS metrics, storage partitions, and running processes.
* **MarinaBox Compute Sandbox**: Isolated script execution sandbox for dynamic diagnostic code prototyping.
* **Llama.cpp Local Inference (`http://localhost:8081`)**: Completely offline reasoning loop using OpenAI-compatible ChatML endpoints.
* **Web Dashboard (`http://localhost:5150`)**: Live dark-mode Web UI dashboard with interactive terminal, diagnostic controls, and scheduled cron jobs.
* **Health Report**: Automatic markdown export (`krokbot_health_report.md`).

## Quickstart & Docker Deployment

The main KrokBot container contains the embedded Llama.cpp runtime, Host Bridge, and Dashboard orchestrator in an all-in-one package:

```bash
# Place your GGUF model into ./models (e.g. Qwen3-4B-Q4_K_M.gguf)
# Build and launch all services with Docker Compose:
docker compose up --build -d
```

Access the services:
- **Web Dashboard**: `http://localhost:5150`
- **Host Bridge API**: `http://localhost:8990`
- **Llama.cpp Server**: `http://localhost:8081/v1/models`

## Local Development Setup

1. Create & activate virtual environment:
   ```powershell
   .\setup_venv.ps1  # Windows PowerShell
   ```

2. Start your local Llama.cpp server or place model in `./models/`:
   ```bash
   python -m llama_cpp.server --model ./models/Qwen3-4B-Q4_K_M.gguf --port 8081 --chat_format chatml
   ```

3. Run KrokBot Launcher:
   ```bash
   python run_krokbot.py
   ```

## Running Tests
```bash
pytest -v
```
