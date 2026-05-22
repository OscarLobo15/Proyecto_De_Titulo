#!/usr/bin/env bash
set -euo pipefail

# Reference Architecture Generator - local development runner
# Usage: ./dev.sh [start|background|stop|restart|status|backend|frontend|logs|setup]

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/.venv"
BACKEND_VENV_FALLBACK="$BACKEND_DIR/venv"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
OPEN_BROWSER="${OPEN_BROWSER:-true}"
BACKEND_RELOAD="${BACKEND_RELOAD:-true}"

BACKEND_LOG="${BACKEND_LOG:-/tmp/reference_generator_backend.log}"
FRONTEND_LOG="${FRONTEND_LOG:-/tmp/reference_generator_frontend.log}"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-/tmp/reference_generator_backend.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/reference_generator_frontend.pid}"

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

browser_tab_is_open() {
  local url="$1"
  local browser
  local result

  command -v osascript >/dev/null 2>&1 || return 1
  command -v pgrep >/dev/null 2>&1 || return 1

  for browser in "Google Chrome" "Microsoft Edge" "Safari"; do
    pgrep -x "$browser" >/dev/null 2>&1 || continue

    result="$(osascript - "$browser" "$url" <<'APPLESCRIPT' 2>/dev/null || true
on run argv
  set browserName to item 1 of argv
  set targetUrl to item 2 of argv

  if browserName is "Safari" then
    tell application "Safari"
      repeat with browserWindow in windows
        repeat with browserTab in tabs of browserWindow
          if (URL of browserTab) starts with targetUrl then return true
        end repeat
      end repeat
    end tell
  else if browserName is "Microsoft Edge" then
    tell application "Microsoft Edge"
      repeat with browserWindow in windows
        repeat with browserTab in tabs of browserWindow
          if (URL of browserTab) starts with targetUrl then return true
        end repeat
      end repeat
    end tell
  else
    tell application "Google Chrome"
      repeat with browserWindow in windows
        repeat with browserTab in tabs of browserWindow
          if (URL of browserTab) starts with targetUrl then return true
        end repeat
      end repeat
    end tell
  end if

  return false
end run
APPLESCRIPT
)"

    [ "$result" = "true" ] && return 0
  done

  return 1
}

open_frontend_once() {
  local url="http://localhost:${FRONTEND_PORT}"

  if [ "$OPEN_BROWSER" != "true" ] || ! command -v open >/dev/null 2>&1; then
    return 0
  fi

  if browser_tab_is_open "$url"; then
    print_line "${DIM}Browser already has ${url} open.${NC}"
    return 0
  fi

  open "$url" >/dev/null 2>&1 || true
}

banner() {
  print_line "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
  print_line "${BLUE}║  Reference Architecture Generator - Dev Environment   ║${NC}"
  print_line "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
}

usage() {
  banner
  cat <<EOF
Usage:
  ./dev.sh [start|background|stop|restart|status|backend|frontend|logs|setup]

Commands:
  start      Start backend + frontend attached to this terminal.
  background Start backend + frontend in background.
  stop       Stop services started by this script.
  restart    Stop then start again.
  status     Show local service status.
  backend    Start only FastAPI.
  frontend   Start only Vite.
  logs       Tail backend and frontend logs.
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
  local backend_pid
  start_backend_with_optional_reload "foreground" backend_pid

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

  open_frontend_once

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

start_backend_process() {
  local mode="$1"

  if [ "$mode" = "reload" ]; then
    "$VENV_DIR/bin/python" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload --reload-dir app
  else
    "$VENV_DIR/bin/python" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  fi
}

backend_failed_due_to_reload_permissions() {
  grep -q "Operation not permitted" "$BACKEND_LOG" 2>/dev/null
}

start_backend_with_optional_reload() {
  local _run_mode="$1"
  local pid_var_name="$2"
  local backend_pid
  local initial_mode="plain"

  if [ "$BACKEND_RELOAD" = "true" ]; then
    initial_mode="reload"
  fi

  > "$BACKEND_LOG"
  start_backend_process "$initial_mode" >"$BACKEND_LOG" 2>&1 &

  backend_pid=$!

  if ! wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 8 && [ "$initial_mode" = "reload" ] && backend_failed_due_to_reload_permissions; then
    print_line "${YELLOW}Backend reload is not permitted in this environment. Retrying without reload...${NC}"
    kill "$backend_pid" >/dev/null 2>&1 || true
    wait "$backend_pid" >/dev/null 2>&1 || true
    > "$BACKEND_LOG"
    start_backend_process "plain" >"$BACKEND_LOG" 2>&1 &

    backend_pid=$!
  fi

  printf -v "$pid_var_name" '%s' "$backend_pid"
}

ensure_backend_deps() {
  venv_is_usable() {
    local candidate_dir="$1"
    [ -x "$candidate_dir/bin/python" ] || return 1
    "$candidate_dir/bin/python" -m pip --version >/dev/null 2>&1 || return 1
    "$candidate_dir/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1 || return 1
  }

  recreate_venv() {
    print_line "${YELLOW}Recreating .venv...${NC}"
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
  }

  if [ ! -d "$VENV_DIR" ] && venv_is_usable "$BACKEND_VENV_FALLBACK"; then
    print_line "${YELLOW}Using existing backend virtualenv at backend/venv.${NC}"
    VENV_DIR="$BACKEND_VENV_FALLBACK"
  fi

  if [ ! -d "$VENV_DIR" ]; then
    print_line "${YELLOW}Python venv not found. Creating .venv...${NC}"
    python3 -m venv "$VENV_DIR"
  fi

  local venv_python="$VENV_DIR/bin/python"
  if [ ! -x "$venv_python" ]; then
    print_line "${YELLOW}Python executable not found inside .venv.${NC}"
    recreate_venv
    venv_python="$VENV_DIR/bin/python"
  fi

  # Some local venvs end up with a broken pip entrypoint. Bootstrap pip from the venv Python when needed.
  if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
    print_line "${YELLOW}pip is missing or broken inside .venv. Restoring it with ensurepip...${NC}"
    "$venv_python" -m ensurepip --upgrade >/dev/null 2>&1
  fi

  # If pip is still unavailable, the virtualenv itself is inconsistent. Recreate it cleanly.
  if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
    print_line "${YELLOW}pip could not be restored inside .venv.${NC}"
    if venv_is_usable "$BACKEND_VENV_FALLBACK"; then
      print_line "${YELLOW}Falling back to backend/venv because it is already usable.${NC}"
      VENV_DIR="$BACKEND_VENV_FALLBACK"
      venv_python="$VENV_DIR/bin/python"
    else
      recreate_venv
      venv_python="$VENV_DIR/bin/python"
      "$venv_python" -m ensurepip --upgrade >/dev/null 2>&1
    fi
  fi

  local marker="$VENV_DIR/.backend_deps_installed"
  if [ ! -f "$marker" ] || [ "$BACKEND_DIR/requirements.txt" -nt "$marker" ] || ! "$venv_python" -c "import fastapi" >/dev/null 2>&1; then
    print_line "${CYAN}Installing backend dependencies...${NC}"
    if ! "$venv_python" -m pip install -q -r "$BACKEND_DIR/requirements.txt"; then
      if [ "$VENV_DIR" != "$BACKEND_VENV_FALLBACK" ] && venv_is_usable "$BACKEND_VENV_FALLBACK"; then
        print_line "${YELLOW}Dependency install failed. Reusing backend/venv instead.${NC}"
        VENV_DIR="$BACKEND_VENV_FALLBACK"
        venv_python="$VENV_DIR/bin/python"
      else
        return 1
      fi
    fi
    touch "$marker"
  else
    print_line "${GREEN}Backend dependencies are synced.${NC}"
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
  else
    print_line "${GREEN}Frontend dependencies are synced.${NC}"
  fi
}

setup_all() {
  ensure_backend_deps
  ensure_frontend_deps
}

start_backend() {
  ensure_backend_deps
  stop_port "backend" "$BACKEND_PORT"

  print_line "${CYAN}Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT}${NC}"
  cd "$BACKEND_DIR"
  local pid
  start_backend_with_optional_reload "background" pid
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
    open_frontend_once
  else
    print_line "${RED}Frontend did not become healthy. Last log lines:${NC}"
    tail -40 "$FRONTEND_LOG" || true
    exit 1
  fi
  cd "$PROJECT_ROOT"
}

stop_all() {
  stop_pid_file "Frontend" "$FRONTEND_PID_FILE"
  stop_pid_file "Backend" "$BACKEND_PID_FILE"
  stop_port "frontend" "$FRONTEND_PORT"
  stop_port "backend" "$BACKEND_PORT"
}

status() {
  banner
  if wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 2; then
    print_line "${GREEN}Backend running${NC}  http://${BACKEND_HOST}:${BACKEND_PORT}"
  else
    print_line "${RED}Backend not running${NC}"
  fi

  if wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" 2; then
    print_line "${GREEN}Frontend running${NC} http://localhost:${FRONTEND_PORT}"
  else
    print_line "${RED}Frontend not running${NC}"
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
  logs)
    tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
    ;;
  setup)
    setup_all
    ;;
  *)
    usage
    ;;
esac
