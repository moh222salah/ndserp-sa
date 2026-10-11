#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SCRIPT="$ROOT/codespace-connection-watchdog.sh"
URL="http://127.0.0.1:8080/login"
PID_FILE="$ROOT/logs/codespace-connection-watchdog.pid"
LOG="$ROOT/logs/codespace-connection-watchdog.log"
WATCHDOG_LOCK="/tmp/ndserp-sa-connection-watchdog.lock"
RUNTIME_LOCK="/tmp/ndserp-sa-runtime-sync.lock"
UI_LOCK="/tmp/ndserp-sa-ui-apply.lock"

mkdir -p "$ROOT/logs"

watchdog_running() {
  local pid cmd cwd
  [ -s "$PID_FILE" ] || return 1
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [ -r "/proc/$pid/cmdline" ] || return 1
  cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  [[ "$cmd" == *"$SCRIPT --run"* && "$cwd" == "$ROOT" ]]
}

if [ "${1:-}" != "--run" ]; then
  if watchdog_running; then
    echo "WATCHDOG=ALREADY_RUNNING"
    echo "WATCHDOG_PID=$(cat "$PID_FILE")"
    exit 0
  fi

  nohup flock -n "$WATCHDOG_LOCK" bash "$SCRIPT" --run \
    >> "$LOG" 2>&1 < /dev/null &
  pid=$!
  printf '%s\n' "$pid" > "$PID_FILE"

  for _ in $(seq 1 5); do
    if watchdog_running; then
      echo "WATCHDOG=RUNNING"
      echo "WATCHDOG_PID=$pid"
      echo "WATCHDOG_LOG=$LOG"
      exit 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  echo "WATCHDOG=FAIL:PROCESS_NOT_CONFIRMED"
  tail -n 30 "$LOG" 2>/dev/null || true
  exit 1
fi

cd "$ROOT"
exec >> "$LOG" 2>&1
echo "WATCHDOG_STARTED=$(date -Is) PID=$$"

http_status() {
  local code
  code="$(curl --connect-timeout 2 --max-time 5 -sS -o /dev/null \
    -w '%{http_code}' "$URL" 2>/dev/null || true)"
  if [[ "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
    printf '%s' "$code"
  else
    printf '000'
  fi
}

while true; do
  code="$(http_status)"
  if [[ "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
    sleep 10
    continue
  fi

  sleep 3
  code="$(http_status)"
  if [[ "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
    continue
  fi

  echo "HTTP_UNAVAILABLE=$(date -Is) HTTP_CODE=$code"
  echo "AUTO_RECOVERY=REQUESTED"

  # Hold both locks while restarting; never overlap a build/deployment.
  if flock -n -o "$RUNTIME_LOCK" \
       flock -n -o "$UI_LOCK" \
       bash -c '
         ROOT="$1"
         sudo -n service mariadb start >/dev/null 2>&1 || true
         NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"
       ' _ "$ROOT"; then
    echo "AUTO_RECOVERY=PASS"
  else
    echo "AUTO_RECOVERY=DEFERRED_OR_FAILED"
    echo "RUNTIME_LOG=$ROOT/logs/codespace-runtime-sync.log"
    echo "BENCH_LOG=$ROOT/logs/codespace-bench.log"
  fi

  sleep 10
done
