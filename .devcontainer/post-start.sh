#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/workspaces/ndserp-sa"
cd "$ROOT"

if ! ss -ltn 2>/dev/null | grep -q ':6000 '; then
  nohup bench start >/tmp/ndserp-sa-codespace.log 2>&1 &
  echo $! >/tmp/ndserp-sa-codespace.pid
  sleep 8
fi

echo "=== NDS ERP SAUDI RUNTIME ==="
ss -ltn 2>/dev/null | grep -E ':6000|:9000|:11000|:13000' || true
curl -I --max-time 10 http://127.0.0.1:6000/ 2>/dev/null || true
tail -40 /tmp/ndserp-sa-codespace.log 2>/dev/null || true
