#!/usr/bin/env bash
set -e

C2_URL="${C2_URL:-http://localhost:5200}"
TOKEN="$1"

if [ -z "$TOKEN" ]; then
  read -p "Enter single-use Enrollment Token (e.g. krok-enroll-xxx): " TOKEN
fi

if [ -z "$TOKEN" ]; then
  echo "Error: Enrollment token is required!"
  exit 1
fi

echo "Deploying KrokBot Bootstrap Agent to C2 ($C2_URL)..."

docker run -d \
  --name krokbot-bootstrap \
  --restart on-failure \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/krokbot:/host_opt_krokbot \
  -e C2_URL="$C2_URL" \
  -e ENROLLMENT_TOKEN="$TOKEN" \
  krokbot-bootstrap:latest
