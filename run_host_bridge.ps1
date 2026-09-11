# Windows PowerShell launcher for KrokBot Host API Bridge
$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Launching KrokBot Host API Bridge (Windows Host)         " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
    $PythonExe = ".\.venv\Scripts\python.exe"
} else {
    $PythonExe = "python"
}

& $PythonExe run_host_bridge.py
