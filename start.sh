#!/bin/bash
# ====================================================================
# RiskMouse - Start / Restart Script (macOS / Linux)
# Auto kill old process -> check env -> start service
# ====================================================================
# Usage:
#   bash start.sh              # start/restart (default port 8787)
#   bash start.sh 5000         # specify port
#   bash start.sh stop         # stop only
# ====================================================================

PORT=${1:-8787}
ACTION=${1:-start}

# If first arg is a number, treat as port with start action
if [[ "$1" =~ ^[0-9]+$ ]]; then
    PORT=$1
    ACTION="start"
fi

# If "stop" action, ignore port from position
if [[ "$1" == "stop" ]]; then
    ACTION="stop"
    PORT=${2:-8787}
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERR]${NC}  $*"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

stop_server() {
    local pids
    pids=$(lsof -ti :"$PORT" 2>/dev/null | tr '\n' ' ')
    if [ -n "${pids// /}" ]; then
        warn "Found old process on port $PORT (PID: $pids), stopping..."
        for pid in $pids; do
            kill -9 "$pid" 2>/dev/null
        done
        sleep 2
        # Verify port is actually free
        local remaining
        remaining=$(lsof -ti :"$PORT" 2>/dev/null)
        if [ -n "$remaining" ]; then
            warn "Port $PORT still in use, retrying..."
            for pid in $remaining; do
                kill -9 "$pid" 2>/dev/null
            done
            sleep 1
        fi
        ok "Old process stopped"
    else
        info "No process on port $PORT, nothing to stop"
    fi
}

check_env() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            err "Created .env from .env.example - please edit and fill in your API Key, then re-run"
            exit 1
        else
            err ".env.example not found either - please create .env first"
            exit 1
        fi
    fi
    ok ".env ready"
}

find_uvicorn() {
    local paths=(
        ".venv/bin/uvicorn"
        ".venv/Scripts/uvicorn"
    )
    for p in "${paths[@]}"; do
        if [ -f "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    err "Virtual environment (.venv) not found - please create it first:"
    err "  python3 -m venv .venv"
    err "  source .venv/bin/activate"
    err "  pip install -r requirements.txt"
    exit 1
}

start_server() {
    local uvicorn_path=$1
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  RiskMouse${NC}"
    echo -e "${CYAN}  Port: $PORT${NC}"
    echo -e "${CYAN}  URL:  http://localhost:$PORT${NC}"
    echo -e "${CYAN}  Docs: http://localhost:$PORT/docs${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    $uvicorn_path backend.app.main:app --host 0.0.0.0 --port "$PORT" --reload
}

echo ""
echo -e "${CYAN}+---------------------------------------+${NC}"
echo -e "${CYAN}|  RiskMouse - Start Script              |${NC}"
echo -e "${CYAN}+---------------------------------------+${NC}"
echo ""

case "$ACTION" in
    stop)
        stop_server
        ok "Service stopped"
        exit 0
        ;;
    *)
        stop_server
        check_env
        uvicorn=$(find_uvicorn)
        start_server "$uvicorn"
        ;;
esac
