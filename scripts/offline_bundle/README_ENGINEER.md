# KrokBot Offline Deployment Bundle (Air-Gapped)

This directory contains the self-contained offline deployment bundle for target machines without Internet access.

## Quickstart for Field Engineers

### Linux / NVIDIA Jetson
1. Copy this folder to target machine or insert USB drive.
2. Run installer:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
3. Verify status:
   ```bash
   docker ps
   docker logs -f krokbot_agent
   ```

### Windows (Docker Desktop / WSL2)
1. Open PowerShell as Administrator.
2. Navigate to this folder and execute:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\install.ps1
   ```

## Directory Structure
- `install.sh`: Linux deployment script
- `install.ps1`: Windows deployment script
- `images/`: Put `krokbot_agent.tar` or `.tar.gz` here
- `models/`: Put GGUF model files (e.g. `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`) here
