#!/usr/bin/env bash
# ============================================================
#  Quickyee - run the server in the background (production)
#
#    ./run_on_background.sh start     start (default)
#    ./run_on_background.sh stop      stop
#    ./run_on_background.sh restart   stop + start
#    ./run_on_background.sh status    running or not
#
#  HOST / PORT come from .env (defaults 0.0.0.0 : 8600).
#  Output goes to logs/server.log, the process id to logs/server.pid.
#  It keeps running after the terminal / SSH session is closed.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

LOG_FILE="logs/server.log"
PID_FILE="logs/server.pid"
mkdir -p logs

# KEY=value from .env (last one wins), else the default
env_value() {
    local value
    value=$(grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d '=' -f 2- | tr -d '\r' || true)
    echo "${value:-$2}"
}

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start() {
    if is_running; then
        echo "Quickyee is already running (PID $(cat "$PID_FILE"))."
        return 0
    fi
    if [ ! -x ".venv/bin/python" ]; then
        echo "[ERROR] .venv not found. Run ./setup.sh first."
        exit 1
    fi
    if [ ! -f ".env" ]; then
        echo "[ERROR] .env not found. Run ./setup.sh first."
        exit 1
    fi

    local host port
    host=$(env_value HOST 0.0.0.0)
    port=$(env_value PORT 8600)

    echo "Starting Quickyee on http://$host:$port ..."
    nohup .venv/bin/python -m uvicorn app.main:app --host "$host" --port "$port" \
        >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 2
    if is_running; then
        echo "Started (PID $(cat "$PID_FILE")). Logs: tail -f $LOG_FILE"
    else
        echo "[ERROR] The server stopped right after starting. Last log lines:"
        tail -n 20 "$LOG_FILE" || true
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if ! is_running; then
        echo "Quickyee is not running."
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid=$(cat "$PID_FILE")
    echo "Stopping Quickyee (PID $pid)..."
    kill "$pid"
    # Up to 15 s for a clean shutdown, then force it
    for _ in $(seq 1 15); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "Stopped."
}

status() {
    if is_running; then
        echo "Quickyee is running (PID $(cat "$PID_FILE")). Logs: $LOG_FILE"
    else
        echo "Quickyee is not running."
    fi
}

case "${1:-start}" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
