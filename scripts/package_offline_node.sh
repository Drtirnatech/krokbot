#!/usr/bin/env bash
set -e

echo "======================================================"
echo "  Packaging KrokBot Offline Deployment Bundle"
echo "======================================================"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/dist/krokbot_offline_bundle"
DIST_ARCHIVE="$REPO_ROOT/dist/krokbot-offline-bundle.tar.gz"

mkdir -p "$OUTPUT_DIR/images" "$OUTPUT_DIR/models"

# 1. Copy install scripts and documentation
cp "$REPO_ROOT/scripts/offline_bundle/install.sh" "$OUTPUT_DIR/"
cp "$REPO_ROOT/scripts/offline_bundle/install.ps1" "$OUTPUT_DIR/"
cp "$REPO_ROOT/scripts/offline_bundle/README_ENGINEER.md" "$OUTPUT_DIR/README.md"
chmod +x "$OUTPUT_DIR/install.sh"

# 2. Export Docker image if requested
if [ "$1" == "--include-image" ] || [ "$1" == "--full" ]; then
  echo "Exporting krokbot_agent:latest container image to $OUTPUT_DIR/images/krokbot_agent.tar..."
  docker save krokbot_agent:latest -o "$OUTPUT_DIR/images/krokbot_agent.tar"
fi

# 3. Copy GGUF models if present
if [ "$1" == "--include-models" ] || [ "$1" == "--full" ]; then
  echo "Copying GGUF models..."
  cp "$REPO_ROOT"/models/*.gguf "$OUTPUT_DIR/models/" 2>/dev/null || true
fi

# 4. Generate bundle tarball
echo "Compressing archive to $DIST_ARCHIVE..."
tar -czf "$DIST_ARCHIVE" -C "$REPO_ROOT/dist" krokbot_offline_bundle

echo "SUCCESS: Bundle created at $DIST_ARCHIVE"
