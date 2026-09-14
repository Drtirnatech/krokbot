#!/usr/bin/env bash
set -e

echo "======================================================"
echo "  KrokBot Air-Gapped Edge Node Offline Installer"
echo "======================================================"

# 1. Check Docker daemon
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running or current user lacks docker group permissions."
  echo "Fix: sudo systemctl start docker && sudo usermod -aG docker \$USER"
  exit 1
fi
echo "[OK] Docker Engine is running and responsive."

# 2. Load Container Image
BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_FILE=$(find "$BUNDLE_DIR/images" -name "*.tar" -o -name "*.tar.gz" 2>/dev/null | head -n 1)

if [ -n "$IMAGE_FILE" ]; then
  echo "[1/3] Loading Docker image from $IMAGE_FILE..."
  docker load -i "$IMAGE_FILE"
  echo "[OK] Container image loaded successfully."
else
  echo "[1/3] No image tarball found in images/ directory. Checking local image cache..."
  if docker image inspect krokbot_agent:latest >/dev/null 2>&1; then
    echo "[OK] Found pre-existing krokbot_agent:latest in local cache."
  else
    echo "ERROR: No container image found. Please place krokbot_agent.tar into images/"
    exit 1
  fi
fi

# 3. Provision Persistent Storage
echo "[2/3] Provisioning persistent storage at /opt/krokbot..."
TARGET_OPT="/opt/krokbot"
if [ ! -w "/opt" ] && [ "$EUID" -ne 0 ]; then
  sudo mkdir -p "$TARGET_OPT/models" "$TARGET_OPT/data"
  sudo chmod -R 775 "$TARGET_OPT"
else
  mkdir -p "$TARGET_OPT/models" "$TARGET_OPT/data"
fi

if compgen -G "$BUNDLE_DIR/models/*.gguf" > /dev/null; then
  echo "Staging GGUF model weights..."
  if [ ! -w "$TARGET_OPT/models" ] && [ "$EUID" -ne 0 ]; then
    sudo cp -u "$BUNDLE_DIR"/models/*.gguf "$TARGET_OPT/models/"
  else
    cp -u "$BUNDLE_DIR"/models/*.gguf "$TARGET_OPT/models/"
  fi
  echo "[OK] Models staged to $TARGET_OPT/models/."
fi

# 4. Launch Container
echo "[3/3] Starting KrokBot Agent container..."
docker rm -f krokbot_agent >/dev/null 2>&1 || true

docker run -d \
  --name krokbot_agent \
  --restart unless-stopped \
  -p 5150:5150 \
  -p 8081:8081 \
  -p 8992:8992 \
  -v "$TARGET_OPT/models:/app/models" \
  -v "$TARGET_OPT/data:/app/data" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  krokbot_agent:latest

echo "======================================================"
echo "  INSTALLATION SUCCESSFUL"
echo "  Agent Web Dashboard:  http://localhost:5150"
echo "  VNC Desktop Stream:   http://localhost:8081"
echo "  Host Bridge API:      http://localhost:8992"
echo "  View Live Logs:       docker logs -f krokbot_agent"
echo "======================================================"
