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

# Verify the actual new Quick Actions styles before contacting the web server.
tr '[:upper:]' '[:lower:]' < "$LOCAL_ASSET" | tr -d '[:space:]' > "$LOCAL_CSS"
for marker in '.amt-quick-actions' '.amt-quick-actions-grid' 'min-height:132px' 'margin-top:auto' 'background:#eef1f4' 'display:none!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_QUICK_ACTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 24
  fi
done
echo "BUILT_QUICK_ACTIONS_CSS=PASS"
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

# Verify the target Quick Actions styles in the CSS actually served to the browser.
tr '[:upper:]' '[:lower:]' < "$SERVED_CSS" | tr -d '[:space:]' > "$LOCAL_CSS"
for marker in '.amt-quick-actions' '.amt-quick-actions-grid' 'min-height:132px' 'margin-top:auto' 'background:#eef1f4' 'display:none!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_QUICK_ACTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 17
  fi
done
echo "SERVED_QUICK_ACTIONS_CSS=PASS"

JS_ASSET_PATH="$("$ROOT/env/bin/python" - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("sites/assets/assets.json").read_text(encoding="utf-8"))
path = manifest.get("amir_theme.bundle.js")
if not isinstance(path, str) or not path:
    raise SystemExit("MISSING_AMIR_THEME_JS_MAPPING")
print(path)
PY
)" || { echo "JS_ASSET_MAPPING=FAIL"; exit 18; }
case "$JS_ASSET_PATH" in
  http://*|https://*) JS_ASSET_URL="$JS_ASSET_PATH" ;;
  /*) JS_ASSET_URL="http://127.0.0.1:$PORT$JS_ASSET_PATH" ;;
  *) JS_ASSET_URL="http://127.0.0.1:$PORT/$JS_ASSET_PATH" ;;
esac
SITE_JS_ASSET="$ROOT/sites/${JS_ASSET_PATH#/}"
REPO_JS_ASSET="$ROOT/${JS_ASSET_PATH#/}"
if [ -f "$SITE_JS_ASSET" ]; then LOCAL_JS_ASSET="$SITE_JS_ASSET"; else LOCAL_JS_ASSET="$REPO_JS_ASSET"; fi
if [ ! -f "$LOCAL_JS_ASSET" ]; then
  echo "BUILT_QUICK_ACTIONS_JS=FAIL:MISSING_FILE:$LOCAL_JS_ASSET"
  exit 19
fi
# Use stable ASCII markers; bundling may encode Arabic literals as Unicode escapes.
for marker in 'amt-quick-actions-title' 'amt-quick-actions-grid' 'Sales Invoice'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_QUICK_ACTIONS_JS=FAIL:MISSING_MARKER:$marker"
    exit 20
  fi
done
SERVED_JS="$(mktemp)"
trap 'rm -f "$LOCAL_CSS" "$SERVED_CSS" "$SERVED_JS"' EXIT
JS_READY=0
for _ in $(seq 1 90); do
  if curl --connect-timeout 2 --max-time 5 -fsS "$JS_ASSET_URL" -o "$SERVED_JS"; then
    JS_READY=1
    break
  fi
  sleep 1
done
if [ "$JS_READY" -ne 1 ]; then
  echo "SERVED_QUICK_ACTIONS_JS=FAIL:HTTP_UNAVAILABLE"
  exit 21
fi
for marker in 'amt-quick-actions-title' 'amt-quick-actions-grid' 'Sales Invoice'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_QUICK_ACTIONS_JS=FAIL:MISSING_MARKER:$marker"
    exit 22
  fi
done
if [ "$(sha256sum "$LOCAL_JS_ASSET" | awk '{print $1}')" != "$(sha256sum "$SERVED_JS" | awk '{print $1}')" ]; then
  echo "SERVED_QUICK_ACTIONS_JS=FAIL:HASH_MISMATCH"
  exit 23
fi
echo "BUILT_QUICK_ACTIONS_JS=PASS"
echo "SERVED_QUICK_ACTIONS_JS=PASS"
echo "SERVED_QUICK_ACTIONS_JS_MATCH=PASS"
echo "HEADER_RUNTIME_VERIFICATION=PASS"
echo "QUICK_ACTIONS_RUNTIME_ASSETS=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "CORE_MODIFICATION=NO"
