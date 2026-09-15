param(
    [string]$Token,
    [string]$C2Url = "http://localhost:5200"
)

if (-not $Token) {
    $Token = Read-Host -Prompt "Enter single-use Enrollment Token (e.g. krok-enroll-xxx)"
}

if (-not $Token) {
    Write-Error "Enrollment token is required!"
    exit 1
}

Write-Host "Deploying KrokBot Bootstrap Agent to C2 ($C2Url)..." -ForegroundColor Green

docker run -d `
  --name krokbot-bootstrap `
  --restart on-failure `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v /opt/krokbot:/host_opt_krokbot `
  -e C2_URL="$C2Url" `
  -e ENROLLMENT_TOKEN="$Token" `
  krokbot-bootstrap:latest
