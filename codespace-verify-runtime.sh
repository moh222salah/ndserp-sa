#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
PORT="8080"
cd "$ROOT"

echo "=== NDS ERP SAUDI — LIVE HEADER VERIFICATION ==="
echo "ROOT=$ROOT"
echo "SOURCE_HEAD=$(git rev-parse HEAD)"
echo "GITHUB_MAIN=$(git rev-parse origin/main 2>/dev/null || git rev-parse HEAD)"

test -s sites/assets/assets.json || { echo "ASSET_MANIFEST=FAIL"; exit 10; }

ASSET_PATH="$("$ROOT/env/bin/python" - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("sites/assets/assets.json").read_text(encoding="utf-8"))
path = manifest.get("amir_theme.bundle.css")
if not isinstance(path, str) or not path:
    raise SystemExit("MISSING_AMIR_THEME_CSS_MAPPING")
print(path)
PY
)" || { echo "ASSET_MAPPING=FAIL"; exit 11; }

case "$ASSET_PATH" in
  http://*|https://*) ASSET_URL="$ASSET_PATH" ;;
  /*) ASSET_URL="http://127.0.0.1:$PORT$ASSET_PATH" ;;
  *) ASSET_URL="http://127.0.0.1:$PORT/$ASSET_PATH" ;;
esac

SITE_ASSET="$ROOT/sites/${ASSET_PATH#/}"
REPO_ASSET="$ROOT/${ASSET_PATH#/}"
if [ -f "$SITE_ASSET" ]; then
  LOCAL_ASSET="$SITE_ASSET"
else
  LOCAL_ASSET="$REPO_ASSET"
fi
if [ ! -f "$LOCAL_ASSET" ]; then
  echo "BUILT_HEADER_CSS=FAIL:MISSING_FILE:$LOCAL_ASSET"
  exit 12
fi

LOCAL_CSS="$(mktemp)"
SERVED_CSS="$(mktemp)"
trap 'rm -f "$LOCAL_CSS" "$SERVED_CSS"' EXIT
tr '[:upper:]' '[:lower:]' < "$LOCAL_ASSET" > "$LOCAL_CSS"
for marker in 'body .navbar' '58px' '#0a2342'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_HEADER_CSS=FAIL:MISSING_MARKER:$marker"
    exit 13
  fi
done
echo "BUILT_HEADER_CSS=PASS"
echo "BUILT_HEADER_CSS_SHA256=$(sha256sum "$LOCAL_ASSET" | awk '{print $1}')"
echo "ASSET_URL=$ASSET_URL"

READY=0
for _ in $(seq 1 90); do
  if curl --connect-timeout 2 --max-time 5 -fsS "$ASSET_URL" -o "$SERVED_CSS"; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "SERVED_HEADER_CSS=FAIL:HTTP_UNAVAILABLE"
  exit 14
fi

tr '[:upper:]' '[:lower:]' < "$SERVED_CSS" > "$LOCAL_CSS"
for marker in 'body .navbar' '58px' '#0a2342'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_HEADER_CSS=FAIL:MISSING_MARKER:$marker"
    exit 15
  fi
done
echo "SERVED_HEADER_CSS=PASS"
echo "SERVED_HEADER_CSS_SHA256=$(sha256sum "$SERVED_CSS" | awk '{print $1}')"
if [ "$(sha256sum "$LOCAL_ASSET" | awk '{print $1}')" != "$(sha256sum "$SERVED_CSS" | awk '{print $1}')" ]; then
  echo "SERVED_HEADER_CSS=FAIL:HASH_MISMATCH"
  exit 16
fi
echo "SERVED_HEADER_CSS_MATCH=PASS"
echo "HEADER_RUNTIME_VERIFICATION=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "CORE_MODIFICATION=NO"
