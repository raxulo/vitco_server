#!/usr/bin/env bash
# ============================================================
#  Quickyee - one-time setup (Linux / macOS)
#  Creates .venv (Python 3.13+), installs requirements and
#  prepares .env, storage and logs. Database tables and the
#  Super Admin are created automatically on the first start.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "==========================================="
echo "   Quickyee Project Setup"
echo "==========================================="

echo ""
echo "1. Finding Python 3.13+ ..."
PY=""
for candidate in python3.14 python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' 2>/dev/null; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "[ERROR] Python 3.13 or newer was not found (python3.14 / python3.13 / python3)."
    exit 1
fi
echo "Using: $PY ($("$PY" --version))"

echo ""
echo "2. Creating Virtual Environment (if not exists)..."
if [ ! -x ".venv/bin/python" ]; then
    "$PY" -m venv .venv
    echo "Virtual Environment created."
else
    echo "Virtual Environment already exists."
fi

echo ""
echo "3. Installing Dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo ""
echo "4. Preparing .env, storage and logs..."
.venv/bin/python scripts/init_env.py
mkdir -p storage/database storage/media logs
chmod +x run_on_cmd.sh run_on_background.sh

echo ""
echo "5. Checking the application loads..."
if .venv/bin/python -c "import app.main" >/dev/null 2>&1; then
    echo "Application loads correctly."
else
    echo "[WARNING] The app did not load. Check .env (SECRET_KEY 32+ chars, ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD)."
fi

echo ""
echo "==========================================="
echo "Setup Complete!"
echo "  Foreground : ./run_on_cmd.sh"
echo "  Background : ./run_on_background.sh start | stop | restart | status"
echo "  (database + Super Admin are created on the first start)"
echo "==========================================="
