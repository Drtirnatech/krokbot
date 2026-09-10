# PowerShell launcher for KrokBot
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Setting up .venv..." -ForegroundColor Yellow
    python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
} else {
    & .\.venv\Scripts\Activate.ps1
}

python run_krokbot.py
