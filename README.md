# KrokBot - Autonomous Workstation Health Agent PoC

KrokBot is a single-agent proof-of-concept inspired by GrokBot. It utilizes a **MarinaBox** virtual compute sandbox, a local **Ollama** LLM model, a **Host API Bridge** daemon (`psutil`), and a **Web Dashboard** to inspect system health autonomously.

## Architecture & Features

* **Host API Bridge (`http://localhost:8990`)**: FastAPI daemon providing secure access to host OS metrics, storage partitions, and running processes.
* **MarinaBox Compute Sandbox**: Isolated script execution sandbox for dynamic diagnostic code prototyping.
* **Local Ollama Integration (`http://localhost:11434`)**: Completely offline reasoning loop.
* **Web Dashboard (`http://localhost:5150`)**: Live dark-mode Web UI dashboard.
* **Health Report**: Automatic markdown export (`krokbot_health_report.md`).

## Quickstart & Virtual Environment Setup

### Option A: Using Setup Script (Automated)

* **PowerShell**:
  ```powershell
  .\setup_venv.ps1
  ```
* **Windows CMD**:
  ```cmd
  setup_venv.bat
  ```
* **Linux / macOS / Git Bash**:
  ```bash
  chmod +x setup_venv.sh && ./setup_venv.sh
  ```

### Option B: Manual Setup

1. Create & activate virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # Windows PowerShell
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure Ollama is running locally:
```bash
ollama run llama3.2
```

3. Run KrokBot:
```bash
python -m krokbot.main
```

4. View Dashboard & Report:
- Web UI: `http://localhost:8080`
- Report: `krokbot_health_report.md`

## Running Tests
```bash
pytest -v
```
