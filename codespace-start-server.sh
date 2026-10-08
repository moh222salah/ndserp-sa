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

echo "=== NDS ERP SAUDI — ENSURE BENCH SERVER ==="
if http_ready; then
  echo "BENCH_SERVER=ALREADY_SERVING"
elif pgrep -af '[b]ench start|[h]oncho start' >/dev/null 2>&1; then
  echo "BENCH_SERVER=PROCESS_ALREADY_RUNNING"
else
  nohup bench start > logs/codespace-bench.log 2>&1 &
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
