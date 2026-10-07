#!/usr/bin/env bash
set -Eeop pipefail

ROOT="/workspaces/ndserp-sa"
cd "$ROOT"

if ! ss -ltn 2>/dev/null | grep -q ':6000 '; then
  nohup bench start >/tmp/ndserp-sa-codespace.log 2>&1 &
  echo $! >/tmp/ndserp-sa-codespace.pid
fi

READY=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 http://127.0.0.1:6000/login >/tmp/ndserp-sa-login.html 2>/dev/null; then
    READY=1
    break
  fi
  sleep 2
done

echo "=== NDS ERP SAUDI RUNTIME ==="
ss -ltn 2>/dev/null | grep -E ':6000|:9000|:11000|:13000' || true

if [ "$READY" -eq 1 ]; then
  echo "HTTP_6000=PASS"
  echo "http://127.0.0.1:6000/"
echo "URL=http://127.0.0.1:6000/"
else
  echo "HTTP_6000=FAIL"
  echo "--- Runtime log ---"
  tail -80 /tmp/ndserp-sa-codespace.log 2>/dev/null || true
  exit 1
fi

./env/bin/python -c 'import frappe; print("FRAPPE_IMPORT=PASS")'
bench --site ndserpsa.nds-sa.com list-apps
