#!/usr/bin/env bash
set -euo pipefail

# Test Proj2 - local development runner
# Usage: ./dev.sh [start|background|stop|restart|status|backend|frontend|services|logs|setup]

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
SERVICES_DIR="$PROJECT_ROOT/services"
VENV_DIR="$PROJECT_ROOT/.venv"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SERVICE_TEMPLATE_PORT="${SERVICE_TEMPLATE_PORT:-8002}"
OPEN_BROWSER="${OPEN_BROWSER:-true}"

BACKEND_LOG="${BACKEND_LOG:-/tmp/test-proj2_backend.log}"
FRONTEND_LOG="${FRONTEND_LOG:-/tmp/test-proj2_frontend.log}"
SERVICE_TEMPLATE_LOG="${SERVICE_TEMPLATE_LOG:-/tmp/test-proj2_service_template.log}"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-/tmp/test-proj2_backend.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/test-proj2_frontend.pid}"
SERVICE_TEMPLATE_PID_FILE="${SERVICE_TEMPLATE_PID_FILE:-/tmp/test-proj2_service_template.pid}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

print_line() {
  printf "%b\n" "$1"
}

banner() {
  print_line "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
  print_line "${BLUE}║  Test Proj2 - Dev Environment${NC}"
  print_line "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
}

usage() {
  banner
  cat <<EOF
Usage:
  ./dev.sh [start|background|stop|restart|status|backend|frontend|services|logs|setup]

Commands:
  start      Start backend + frontend attached to this terminal.
  background Start backend + frontend in background.
  stop       Stop local services.
  restart    Stop then start again.
  status     Show local service status.
  backend    Start only FastAPI.
  frontend   Start only React.
  services   Start optional service skeletons.
  logs       Tail local logs.
  setup      Create venv and install dependencies.
EOF
}

foreground() {
  banner
  setup_all

  stop_port "backend" "$BACKEND_PORT"


  stop_port "frontend" "$FRONTEND_PORT"



  print_line "${CYAN}Starting backend in foreground mode...${NC}"
  cd "$BACKEND_DIR"
  "$VENV_DIR/bin/python" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
  local backend_pid=$!

  if ! wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 30; then
    print_line "${RED}Backend did not become healthy. Last log lines:${NC}"
    tail -40 "$BACKEND_LOG" || true
    kill "$backend_pid" >/dev/null 2>&1 || true
    exit 1
  fi

  print_line "${GREEN}Backend ready.${NC} http://${BACKEND_HOST}:${BACKEND_PORT}"


  print_line "${CYAN}Starting frontend attached to this terminal...${NC}"
  print_line "${DIM}Press Ctrl+C to stop both services.${NC}"
  print_line "${GREEN}Frontend:${NC} http://localhost:${FRONTEND_PORT}"

  print_line "${GREEN}Swagger:${NC}  http://${BACKEND_HOST}:${BACKEND_PORT}/docs"


  if [ "$OPEN_BROWSER" = "true" ] && command -v open >/dev/null 2>&1; then
    open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 || true
  fi

  cleanup_foreground() {

    print_line "${DIM}Stopping backend...${NC}"
    kill "$backend_pid" >/dev/null 2>&1 || true

  }
  trap cleanup_foreground EXIT INT TERM

  cd "$FRONTEND_DIR"
  node "$FRONTEND_DIR/node_modules/vite/bin/vite.js" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"

}

is_running() {
  local pid="${1:-}"
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

read_pid_file() {
  local file="$1"
  [ -f "$file" ] && cat "$file"
}

write_pid_file() {
  local file="$1"
  local pid="$2"
  printf "%s" "$pid" > "$file"
}

stop_pid_file() {
  local label="$1"
  local file="$2"
  local pid
  pid="$(read_pid_file "$file" || true)"

  if is_running "$pid"; then
    print_line "${CYAN}Stopping ${label} pid ${pid}${NC}"
    kill "$pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 10); do
      is_running "$pid" || break
      sleep 1
    done
    is_running "$pid" && kill -9 "$pid" >/dev/null 2>&1 || true
  else
    print_line "${DIM}${label} is not running.${NC}"
  fi

  rm -f "$file"
}

stop_port() {
  local label="$1"
  local port="$2"
  local pids
  pids="$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    print_line "${CYAN}Freeing ${label} port ${port}${NC}"
    kill $pids >/dev/null 2>&1 || true
    sleep 1
  fi
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-30}"
  for _ in $(seq 1 "$attempts"); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

ensure_backend_deps() {
  if [ ! -d "$VENV_DIR" ]; then
    print_line "${YELLOW}Python venv not found. Creating .venv...${NC}"
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  local marker="$VENV_DIR/.backend_deps_installed"
  if [ ! -f "$marker" ] || [ "$BACKEND_DIR/requirements.txt" -nt "$marker" ]; then
    print_line "${CYAN}Installing backend dependencies...${NC}"
    pip install -q -r "$BACKEND_DIR/requirements.txt"
    touch "$marker"
  fi
}

ensure_frontend_deps() {

  if ! command -v npm >/dev/null 2>&1; then
    print_line "${RED}Node.js/npm is required.${NC}"
    exit 1
  fi

  if [ ! -d "$FRONTEND_DIR/node_modules" ] || [ "$FRONTEND_DIR/package.json" -nt "$FRONTEND_DIR/node_modules" ]; then
    print_line "${CYAN}Installing frontend dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install
    cd "$PROJECT_ROOT"
  fi
}

ensure_service_deps() {

  [ -d "$SERVICES_DIR" ] || return 0
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  for req_file in "$SERVICES_DIR"/*/requirements.txt; do
    [ -f "$req_file" ] || continue
    local service_name
    service_name="$(basename "$(dirname "$req_file")")"
    local marker="$VENV_DIR/.service_${service_name}_deps_installed"
    if [ ! -f "$marker" ] || [ "$req_file" -nt "$marker" ]; then
      print_line "${CYAN}Installing service deps: ${service_name}${NC}"
      pip install -q -r "$req_file"
      touch "$marker"
    fi
  done
}

setup_all() {
  ensure_backend_deps
  ensure_frontend_deps
  ensure_service_deps
}

start_backend() {

  ensure_backend_deps
  stop_port "backend" "$BACKEND_PORT"
  print_line "${CYAN}Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT}${NC}"
  > "$BACKEND_LOG"
  cd "$BACKEND_DIR"
  nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 </dev/null &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  write_pid_file "$BACKEND_PID_FILE" "$pid"

  if wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 30; then
    sleep 1
    if ! is_running "$pid"; then
      print_line "${RED}Backend exited after startup. Last log lines:${NC}"
      tail -40 "$BACKEND_LOG" || true
      exit 1
    fi
    print_line "${GREEN}Backend ready.${NC} ${DIM}Swagger: http://${BACKEND_HOST}:${BACKEND_PORT}/docs${NC}"
  else
    print_line "${RED}Backend did not become healthy. Last log lines:${NC}"
    tail -40 "$BACKEND_LOG" || true
    exit 1
  fi
  cd "$PROJECT_ROOT"
}

start_frontend() {

  ensure_frontend_deps
  stop_port "frontend" "$FRONTEND_PORT"
  print_line "${CYAN}Starting frontend on http://localhost:${FRONTEND_PORT}${NC}"
  > "$FRONTEND_LOG"
  cd "$FRONTEND_DIR"
  nohup node "$FRONTEND_DIR/node_modules/vite/bin/vite.js" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 </dev/null &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  write_pid_file "$FRONTEND_PID_FILE" "$pid"

  if wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" 30; then
    sleep 1
    if ! is_running "$pid"; then
      print_line "${RED}Frontend exited after startup. Last log lines:${NC}"
      tail -40 "$FRONTEND_LOG" || true
      exit 1
    fi
    print_line "${GREEN}Frontend ready.${NC} http://localhost:${FRONTEND_PORT}"
    print_line "${DIM}Alternative: http://127.0.0.1:${FRONTEND_PORT}${NC}"
    if [ "$OPEN_BROWSER" = "true" ] && command -v open >/dev/null 2>&1; then
      open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 || true
    fi
  else
    print_line "${RED}Frontend did not become healthy. Last log lines:${NC}"
    tail -40 "$FRONTEND_LOG" || true
    exit 1
  fi
  cd "$PROJECT_ROOT"
}

start_services() {

  [ -d "$SERVICES_DIR/template" ] || {
    print_line "${DIM}No service skeletons configured.${NC}"
    return 0
  }
  ensure_backend_deps
  ensure_service_deps
  stop_port "service-template" "$SERVICE_TEMPLATE_PORT"
  print_line "${CYAN}Starting template service on http://127.0.0.1:${SERVICE_TEMPLATE_PORT}${NC}"
  > "$SERVICE_TEMPLATE_LOG"
  cd "$SERVICES_DIR/template"
  nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$SERVICE_TEMPLATE_PORT" >"$SERVICE_TEMPLATE_LOG" 2>&1 </dev/null &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  write_pid_file "$SERVICE_TEMPLATE_PID_FILE" "$pid"

  if wait_for_url "http://127.0.0.1:${SERVICE_TEMPLATE_PORT}/health" 30; then
    sleep 1
    if ! is_running "$pid"; then
      print_line "${RED}Template service exited after startup. Last log lines:${NC}"
      tail -40 "$SERVICE_TEMPLATE_LOG" || true
      exit 1
    fi
    print_line "${GREEN}Template service ready.${NC}"
  else
    print_line "${RED}Template service did not become healthy.${NC}"
    tail -40 "$SERVICE_TEMPLATE_LOG" || true
    exit 1
  fi
  cd "$PROJECT_ROOT"
}

stop_all() {
  stop_pid_file "Template service" "$SERVICE_TEMPLATE_PID_FILE"
  stop_pid_file "Frontend" "$FRONTEND_PID_FILE"
  stop_pid_file "Backend" "$BACKEND_PID_FILE"
  stop_port "service-template" "$SERVICE_TEMPLATE_PORT"
  stop_port "frontend" "$FRONTEND_PORT"
  stop_port "backend" "$BACKEND_PORT"
}

status() {
  banner
  wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 2 \
    && print_line "${GREEN}Backend running${NC}  http://${BACKEND_HOST}:${BACKEND_PORT}" \
    || print_line "${RED}Backend not running${NC}"
  wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" 2 \
    && print_line "${GREEN}Frontend running${NC} http://localhost:${FRONTEND_PORT}" \
    || print_line "${RED}Frontend not running${NC}"
  if [ -d "$SERVICES_DIR/template" ]; then
    wait_for_url "http://127.0.0.1:${SERVICE_TEMPLATE_PORT}/health" 2 \
      && print_line "${GREEN}Template service running${NC} http://127.0.0.1:${SERVICE_TEMPLATE_PORT}" \
      || print_line "${YELLOW}Template service not running${NC}"
  fi
}

case "${1:-help}" in
  start)
    foreground
    ;;
  background)
    banner
    start_backend

    start_frontend
    print_line "${GREEN}All services started.${NC}"
    ;;
  stop)
    stop_all
    print_line "${GREEN}All services stopped.${NC}"
    ;;
  restart)
    stop_all
    start_backend

    start_frontend
    ;;
  status)
    status
    ;;
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  services)
    start_services
    ;;
  logs)
    tail -f "$BACKEND_LOG" "$FRONTEND_LOG" "$SERVICE_TEMPLATE_LOG" 2>/dev/null || true
    ;;
  setup)
    setup_all
    ;;
  *)
    usage
    ;;
esac
