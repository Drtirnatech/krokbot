# PowerShell script to create and set up the KrokBot virtual environment

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  KrokBot Virtual Environment Setup (.venv)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Create .venv if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "[1/3] Creating Python virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[1/3] Virtual environment (.venv) already exists." -ForegroundColor Green
}

# 2. Activate virtual environment
Write-Host "[2/3] Activating virtual environment..." -ForegroundColor Yellow
$activateScript = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
} else {
    Write-Host "Activation script not found at $activateScript" -ForegroundColor Red
    exit 1
}

# 3. Upgrade pip and install dependencies
Write-Host "[3/3] Upgrading pip and installing requirements.txt..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  KrokBot Virtual Environment Setup Complete!" -ForegroundColor Green
Write-Host "  To activate in PowerShell, run:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "  To start KrokBot, run:           python -m krokbot.main" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
