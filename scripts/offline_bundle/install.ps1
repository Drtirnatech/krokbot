<#
.SYNOPSIS
    KrokBot Air-Gapped Offline Installer for Windows (Docker Desktop / WSL2)
#>

$ErrorActionPreference = "Stop"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  KrokBot Air-Gapped Offline Installer (Windows)     " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# 1. Verify Docker CLI and engine
try {
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
    if (-not $dockerVersion) {
        throw "Docker engine not responding"
    }
    Write-Host "[OK] Docker Engine is running (v$dockerVersion)." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker Desktop is not running. Please launch Docker Desktop and retry." -ForegroundColor Red
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 2. Load Container Image
$imageTar = Get-ChildItem -Path "$ScriptDir\images" -Filter "*.tar*" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($imageTar) {
    Write-Host "[1/3] Loading Docker image from $($imageTar.FullName)..." -ForegroundColor Yellow
    docker load -i $imageTar.FullName
    Write-Host "[OK] Image loaded." -ForegroundColor Green
} else {
    Write-Host "[1/3] Checking local image cache for krokbot_agent:latest..." -ForegroundColor Yellow
    $inspect = docker image inspect krokbot_agent:latest 2>$null
    if (-not $inspect) {
        Write-Host "ERROR: No container image found. Please place krokbot_agent.tar into images\" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Using existing krokbot_agent:latest." -ForegroundColor Green
}

# 3. Provision Persistent Storage
$OptDir = "C:\opt\krokbot"
Write-Host "[2/3] Provisioning persistent storage at $OptDir..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$OptDir\models" | Out-Null
New-Item -ItemType Directory -Force -Path "$OptDir\data" | Out-Null

$modelFiles = Get-ChildItem -Path "$ScriptDir\models\*.gguf" -ErrorAction SilentlyContinue
if ($modelFiles) {
    foreach ($m in $modelFiles) {
        Copy-Item -Path $m.FullName -Destination "$OptDir\models\" -Force
        Write-Host "[OK] Copied model $($m.Name) to $OptDir\models\" -ForegroundColor Green
    }
}

# 4. Launch Container
Write-Host "[3/3] Starting KrokBot Agent container..." -ForegroundColor Yellow
docker rm -f krokbot_agent 2>$null | Out-Null

docker run -d `
  --name krokbot_agent `
  --restart unless-stopped `
  -p 5150:5150 `
  -p 8081:8081 `
  -p 8992:8992 `
  -v "${OptDir}\models:/app/models" `
  -v "${OptDir}\data:/app/data" `
  -v /var/run/docker.sock:/var/run/docker.sock `
  krokbot_agent:latest

Write-Host "======================================================" -ForegroundColor Green
Write-Host "  INSTALLATION SUCCESSFUL" -ForegroundColor Green
Write-Host "  Agent Web Dashboard:  http://localhost:5150" -ForegroundColor Cyan
Write-Host "  VNC Desktop Stream:   http://localhost:8081" -ForegroundColor Cyan
Write-Host "  Host Bridge API:      http://localhost:8992" -ForegroundColor Cyan
Write-Host "  View Live Logs:       docker logs -f krokbot_agent" -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Green
