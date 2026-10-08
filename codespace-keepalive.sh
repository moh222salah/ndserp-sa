#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
PORT="8080"
INTERVAL="${CODESPACE_KEEPALIVE_INTERVAL:-5}"
LOG="$ROOT/logs/codespace-bench.log"
LOCK="$ROOT/logs/codespace-keepalive.lock"
PID_FILE="$ROOT/logs/codespace-keepalive.pid"

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

mkdir -p "$ROOT/logs"

# Only one supervisor instance is allowed for this Codespace.
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "KEEPALIVE=ALREADY_RUNNING"
  exit 0
fi

printf '%s\n' "$$" > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

echo "=== NDS ERP SAUDI — CODESPACE KEEPALIVE ==="
echo "ROOT=$ROOT"
echo "SITE=$SITE"
echo "PORT=$PORT"
echo "KEEPALIVE_PID=$$"

ensure_services() {
  sudo service mariadb start >/dev/null 2>&1 || true
  sudo service redis-server start >/dev/null 2>&1 || true
}

bench_running() {
  pgrep -af '(^|[ /])bench start([ ]|$)' >/dev/null 2>&1
}

runtime_ready() {
  curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:${PORT}/login"
}

start_bench() {
  echo "BENCH_START=REQUESTED"
  nohup bench start >"$LOG" 2>&1 < /dev/null &
  echo "BENCH_PID=$!"
}

while true; do
  ensure_services

  if runtime_ready; then
    echo "RUNTIME_HTTP=PASS"
  else
    echo "RUNTIME_HTTP=DOWN"

    if bench_running; then
      echo "BENCH_PROCESS=RUNNING_WAIT"
    else
      start_bench
    fi
  fi

  sleep "$INTERVAL"
done
