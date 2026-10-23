#!/usr/bin/env bash
# ============================================================
#  Quickyee - build the single-file executable (Linux / Ubuntu)
#
#  Produces: dist/quickyee   (one file, no .py inside)
#
#  On start it asks what to ship alongside the binary:
#    clean - exe only; it creates a fresh empty database and no
#            images on first run.
#    keep  - also copy the current storage/ (database + uploaded
#            images) into dist/, so the deployment keeps today's data.
#
#  You can skip the question:  ./build_exe.sh clean   or   ./build_exe.sh keep
#
#  Run this ON Ubuntu (PyInstaller does not cross-compile).
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

# ---- Ask clean vs keep (unless given as an argument) -------
MODE="${1:-}"
if [ -z "$MODE" ]; then
    echo "What should the build include?"
    echo "  [c] Clean  - exe only; fresh empty database and no images on first run"
    echo "  [k] Keep   - also copy current storage/ (database + images) next to the exe"
    read -r -p "Choose [c/k] (default: c): " ans
    case "$ans" in
        k|K|keep|KEEP) MODE="keep" ;;
        *) MODE="clean" ;;
    esac
fi
case "$MODE" in
    clean|keep) ;;
    *) echo "[ERROR] Unknown option '$MODE' (use clean or keep)."; exit 1 ;;
esac
echo "==> Build mode: $MODE"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "==> .venv not found - creating it with a supported Python (3.13+)"
    BASEPY=""
    for candidate in python3.14 python3.13 python3; do
        if command -v "$candidate" >/dev/null 2>&1 &&
            "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' 2>/dev/null; then
            BASEPY="$candidate"
            break
        fi
    done
    if [ -z "$BASEPY" ]; then
        echo "[ERROR] Python 3.13 or newer was not found (python3.14 / python3.13 / python3)."
        exit 1
    fi
    echo "==> Using $BASEPY ($("$BASEPY" --version)) to create .venv"
    "$BASEPY" -m venv .venv
fi

# Activate the venv (the steps below also call "$PY" directly, so this is safe
# even if activation is unavailable).
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

echo "==> Installing build + app dependencies into .venv"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt
"$PY" -m pip install --quiet pyinstaller

echo "==> Building single-file executable"
"$PY" -m PyInstaller --clean --noconfirm quickyee.spec

# ---- Decide what data travels with the binary --------------
# This only touches dist/ - your project's storage/ is never deleted.
rm -rf dist/storage
if [ "$MODE" = "keep" ]; then
    if [ -d storage ]; then
        echo "==> Keeping current data: copying storage/ (database + images) into dist/"
        cp -r storage dist/storage
    else
        echo "==> No storage/ found - nothing to copy; the exe will start fresh."
    fi
else
    echo "==> Clean build: no database or images shipped; the exe starts fresh."
fi

echo
echo "Done. Output folder: dist/"
echo "  dist/quickyee        (the binary)"
[ "$MODE" = "keep" ] && echo "  dist/storage/        (database + images carried over)"
echo "Copy dist/ and a .env to the server, then from inside it:  ./quickyee"
