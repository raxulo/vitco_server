#!/usr/bin/env bash
# ============================================================
#  Quickyee - run the server in this terminal (foreground)
#  HOST / PORT come from .env (defaults 0.0.0.0 : 8600).
#  Ctrl+C stops it. Pass --reload to restart on code changes.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "==========================================="
echo "  Starting Quickyee Server"
echo "==========================================="

if [ ! -x ".venv/bin/python" ]; then
    echo "[ERROR] .venv not found. Run ./setup.sh first."
    exit 1
fi
if [ ! -f ".env" ]; then
    echo "[ERROR] .env not found. Run ./setup.sh first."
    exit 1
fi

# KEY=value from .env (last one wins), else the default
env_value() {
    local value
    value=$(grep -E "^$1=" .env | tail -n 1 | cut -d '=' -f 2- | tr -d '\r' || true)
    echo "${value:-$2}"
}
HOST=$(env_value HOST 0.0.0.0)
PORT=$(env_value PORT 8600)

echo "Server: http://$HOST:$PORT   (Ctrl+C to stop)"
.venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT" "$@"

echo ""
echo "Server stopped."
