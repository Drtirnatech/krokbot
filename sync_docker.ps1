# Fast sync / reload script for running KrokBot Docker instance
$ErrorActionPreference = "Stop"

Write-Host "Syncing KrokBot Docker container..." -ForegroundColor Cyan

# Check if krokbot_agent is running
$running = docker ps -q --filter "name=krokbot_agent"
if ($running) {
    Write-Host "Restarting krokbot_agent with live mounted workspace code..." -ForegroundColor Yellow
    docker restart krokbot_agent
    Write-Host "KrokBot container restarted successfully!" -ForegroundColor Green
    Write-Host "Dashboard: http://localhost:5150" -ForegroundColor Cyan
} else {
    Write-Host "Container not running. Starting with docker compose up -d..." -ForegroundColor Yellow
    docker compose up -d
    Write-Host "KrokBot started!" -ForegroundColor Green
}
