#!/bin/sh
set -e

echo "Starting KrokBot Bootstrap Agent..."
exec python3 /app/bootstrap.py "$@"
