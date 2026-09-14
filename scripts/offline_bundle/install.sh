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

# 4. Multi-Agent Port & Container Conflict Resolution
echo "[3/3] Planning container allocation and checking port availability..."
EXISTING_CONTAINERS=$(docker ps -a --format '{{.Names}}' 2>/dev/null || true)

CONTAINER_NAME="krokbot_agent"
IDX=1
while echo "$EXISTING_CONTAINERS" | grep -qx "$CONTAINER_NAME"; do
  IDX=$((IDX + 1))
  CONTAINER_NAME="krokbot_agent_${IDX}"
done

# Allocate unique Web Dashboard port (base 5150)
WEB_PORT=5150
while docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$WEB_PORT->" || (exec 6<>/dev/tcp/127.0.0.1/$WEB_PORT) 2>/dev/null; do
  exec 6>&- 2>/dev/null || true
  WEB_PORT=$((WEB_PORT + 1))
done
exec 6>&- 2>/dev/null || true

# Allocate unique VNC port (base 8081)
VNC_PORT=8081
while docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$VNC_PORT->" || (exec 6<>/dev/tcp/127.0.0.1/$VNC_PORT) 2>/dev/null; do
  exec 6>&- 2>/dev/null || true
  VNC_PORT=$((VNC_PORT + 1))
done
exec 6>&- 2>/dev/null || true

# Allocate unique Host Bridge port (base 8992)
BRIDGE_PORT=8992
while docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$BRIDGE_PORT->" || (exec 6<>/dev/tcp/127.0.0.1/$BRIDGE_PORT) 2>/dev/null; do
  exec 6>&- 2>/dev/null || true
  BRIDGE_PORT=$((BRIDGE_PORT + 1))
done
exec 6>&- 2>/dev/null || true

DATA_DIR="$TARGET_OPT/data"
if [ "$IDX" -gt 1 ]; then
  DATA_DIR="$TARGET_OPT/data_${IDX}"
  if [ ! -w "/opt" ] && [ "$EUID" -ne 0 ]; then
    sudo mkdir -p "$DATA_DIR"
    sudo chmod -R 775 "$DATA_DIR"
  else
    mkdir -p "$DATA_DIR"
  fi
  echo "Notice: Detected existing agent container. Co-locating secondary agent '$CONTAINER_NAME' on port $WEB_PORT with isolated data '$DATA_DIR'."
fi

echo "Starting container '$CONTAINER_NAME' (Ports: Web=$WEB_PORT, VNC=$VNC_PORT, Bridge=$BRIDGE_PORT)..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "$WEB_PORT:5150" \
  -p "$VNC_PORT:8081" \
  -p "$BRIDGE_PORT:8992" \
  -v "$TARGET_OPT/models:/app/models" \
  -v "$DATA_DIR:/app/data" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  krokbot_agent:latest

echo "======================================================"
echo "  INSTALLATION SUCCESSFUL: $CONTAINER_NAME"
echo "  Agent Web Dashboard:  http://localhost:$WEB_PORT"
echo "  VNC Desktop Stream:   http://localhost:$VNC_PORT"
echo "  Host Bridge API:      http://localhost:$BRIDGE_PORT"
echo "  View Live Logs:       docker logs -f $CONTAINER_NAME"
echo "======================================================"
