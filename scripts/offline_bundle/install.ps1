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

# 4. Multi-Agent Port & Container Conflict Resolution
Write-Host "[3/3] Planning container allocation and checking port availability..." -ForegroundColor Yellow

function Get-NextFreePort($startPort) {
    $port = $startPort
    while ($true) {
        $inUse = $false
        # 1. Check docker ports
        $dockerPorts = docker ps --format '{{.Ports}}' 2>$null
        if ($dockerPorts -match ":$port->") { $inUse = $true }

        # 2. Check local TCP connect
        if (-not $inUse) {
            $tcp = [System.Net.Sockets.TcpClient]::new()
            try {
                $tcp.Connect("127.0.0.1", $port)
                $inUse = $true
                $tcp.Close()
            } catch {
                $inUse = $false
            }
        }

        if (-not $inUse) { return $port }
        $port++
    }
}

# Determine container name and data folder
$existingContainers = docker ps -a --format '{{.Names}}' 2>$null
$containerName = "krokbot_agent"
$idx = 1
while ($existingContainers -contains $containerName) {
    $idx++
    $containerName = "krokbot_agent_$idx"
}

$webPort = Get-NextFreePort 5150
$vncPort = Get-NextFreePort 5155
$bridgePort = Get-NextFreePort 8992
$targetDataDir = if ($idx -eq 1) { "$OptDir\data" } else { "$OptDir\data_$idx" }
New-Item -ItemType Directory -Force -Path $targetDataDir | Out-Null

if ($idx -gt 1) {
    Write-Host "Notice: Detected existing agent container. Co-locating secondary agent '$containerName' on port $webPort with isolated data '$targetDataDir'." -ForegroundColor Magenta
}

Write-Host "Starting container '$containerName' (Ports: Web=$webPort, VNC=$vncPort, Bridge=$bridgePort)..." -ForegroundColor Yellow
docker run -d `
  --name $containerName `
  --restart unless-stopped `
  -p "${webPort}:5150" `
  -p "${vncPort}:5155" `
  -p "${bridgePort}:8992" `
  -v "${OptDir}\models:/app/models" `
  -v "${targetDataDir}:/app/data" `
  -v /var/run/docker.sock:/var/run/docker.sock `
  krokbot_agent:latest

Write-Host "======================================================" -ForegroundColor Green
Write-Host "  INSTALLATION SUCCESSFUL: $containerName" -ForegroundColor Green
Write-Host "  Agent Web Dashboard:  http://localhost:$webPort" -ForegroundColor Cyan
Write-Host "  VNC Desktop Stream:   http://localhost:$vncPort" -ForegroundColor Cyan
Write-Host "  Host Bridge API:      http://localhost:$bridgePort" -ForegroundColor Cyan
Write-Host "  View Live Logs:       docker logs -f $containerName" -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Green
