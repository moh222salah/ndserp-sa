#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
PORT="8080"
URL="http://127.0.0.1:${PORT}/login"

cd "$ROOT"
mkdir -p logs

http_ready() {
  curl --connect-timeout 1 --max-time 2 -fsS "$URL" -o /dev/null
}

bench_pids() {
  local pid cwd
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    [ -e "/proc/$pid/cwd" ] || continue
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    case "$cwd" in
      "$ROOT"|"$ROOT"/*) printf '%s\n' "$pid" ;;
    esac
  done < <(pgrep -f '[b]ench start|[h]oncho start' || true)
}

port_listener_pids() {
  local pids=""
  if command -v ss >/dev/null 2>&1; then
    pids="$(ss -H -ltnp 'sport = :8080' 2>/dev/null |
      grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  fi
  if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -nP -t -iTCP:8080 -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  fi
  printf '%s\n' "$pids" | sed '/^$/d'
}

echo "=== NDS ERP SAUDI — ENSURE BENCH SERVER ==="
echo "ROOT=$ROOT"

if [ "${NDS_FORCE_BENCH_RESTART:-0}" = "1" ]; then
  echo "BENCH_RESTART=REQUESTED"
  mapfile -t old_pids < <(bench_pids)
  for pid in "${old_pids[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done

  for _ in $(seq 1 20); do
    mapfile -t remaining_pids < <(bench_pids)
    if ! http_ready && [ "${#remaining_pids[@]}" -eq 0 ]; then
      break
    fi
    sleep 1
  done

  mapfile -t remaining_pids < <(bench_pids)
  if [ "${#remaining_pids[@]}" -gt 0 ]; then
    for pid in "${remaining_pids[@]}"; do
      kill -KILL "$pid" 2>/dev/null || true
    done
  fi

  for _ in $(seq 1 10); do
    mapfile -t remaining_pids < <(bench_pids)
    if ! http_ready && [ "${#remaining_pids[@]}" -eq 0 ]; then
      break
    fi
    sleep 1
  done

  # A terminated bench supervisor can leave an orphaned web worker bound to 8080.
  # This port is reserved for the Saudi Codespace Bench runtime.
  if http_ready; then
    mapfile -t listener_pids < <(port_listener_pids)
    if [ "${#listener_pids[@]}" -gt 0 ]; then
      echo "STALE_HTTP_LISTENERS=${listener_pids[*]}"
      for pid in "${listener_pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
      done
      for _ in $(seq 1 10); do
        if ! http_ready; then break; fi
        sleep 1
      done
      if http_ready; then
        mapfile -t listener_pids < <(port_listener_pids)
        for pid in "${listener_pids[@]}"; do
          kill -KILL "$pid" 2>/dev/null || true
        done
        for _ in $(seq 1 10); do
          if ! http_ready; then break; fi
          sleep 1
        done
      fi
    fi
  fi

  mapfile -t remaining_pids < <(bench_pids)
  if http_ready || [ "${#remaining_pids[@]}" -gt 0 ]; then
    echo "BENCH_RESTART=FAIL:OLD_RUNTIME_STILL_ACTIVE"
    echo "BENCH_PIDS=${remaining_pids[*]:-unknown}"
    echo "HTTP_LISTENER_PIDS=$(port_listener_pids | paste -sd, -)"
    exit 2
  fi
  echo "BENCH_RESTART=PASS"
fi

if http_ready; then
  echo "BENCH_SERVER=ALREADY_SERVING"
elif [ -n "$(bench_pids)" ]; then
  echo "BENCH_SERVER=PROCESS_ALREADY_RUNNING"
else
  nohup bench start > logs/codespace-bench.log 2>&1 < /dev/null &
  echo "BENCH_START_REQUESTED=PASS"
fi

for _ in $(seq 1 90); do
  if http_ready; then
    echo "BENCH_SERVER=PASS"
    echo "BENCH_PORT=$PORT"
    exit 0
  fi
  sleep 1
done

echo "BENCH_SERVER=FAIL:HTTP_NOT_READY"
tail -n 80 logs/codespace-bench.log 2>/dev/null || true
exit 1
