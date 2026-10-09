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
for marker in '.amt-quick-actions' '.amt-quick-actions-grid' '.amt-quick-actions-track' 'height:104px' 'min-height:104px' 'width:36px' 'width:20px' 'margin-top:auto' 'background:#eef1f4' 'display:none!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_QUICK_ACTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 24
  fi
done
echo "BUILT_QUICK_ACTIONS_CSS=PASS"
for marker in '.nds-warehouse-workspace' 'border-block-start:3pxsolid#0a2342'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_WAREHOUSE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 26
  fi
done
echo "BUILT_WAREHOUSE_WORKSPACE_CSS=PASS"
for marker in '.amt-accounts-workspace' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#bd5548'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_ACCOUNTS_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 30
  fi
done
echo "BUILT_ACCOUNTS_WORKSPACE_CSS=PASS"
for marker in '.nds-sales-workspace-redesign' '#page-workspaces' '#d4af37'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_SALES_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 34
  fi
done
echo "BUILT_SALES_WORKSPACE_CSS=PASS"
for marker in '.nds-purchase-workspace-redesign' '#page-workspaces' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#c58b3c' 'grid-column:span7' 'grid-column:span5' 'border-collapse:separate'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_PURCHASE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 38
  fi
done
echo "BUILT_PURCHASE_WORKSPACE_CSS=PASS"
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
for marker in '.amt-quick-actions' '.amt-quick-actions-grid' '.amt-quick-actions-track' 'height:104px' 'min-height:104px' 'width:36px' 'width:20px' 'margin-top:auto' 'background:#eef1f4' 'display:none!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_QUICK_ACTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 17
  fi
done
echo "SERVED_QUICK_ACTIONS_CSS=PASS"
for marker in '.nds-warehouse-workspace' 'border-block-start:3pxsolid#0a2342'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_WAREHOUSE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 27
  fi
done
echo "SERVED_WAREHOUSE_WORKSPACE_CSS=PASS"
for marker in '.amt-accounts-workspace' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#bd5548'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_ACCOUNTS_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 31
  fi
done
echo "SERVED_ACCOUNTS_WORKSPACE_CSS=PASS"
for marker in '.nds-sales-workspace-redesign' '#page-workspaces' '#d4af37'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_SALES_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 35
  fi
done
echo "SERVED_SALES_WORKSPACE_CSS=PASS"
for marker in '.nds-purchase-workspace-redesign' '#page-workspaces' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#c58b3c' 'grid-column:span7' 'grid-column:span5' 'border-collapse:separate'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_PURCHASE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 39
  fi
done
echo "SERVED_PURCHASE_WORKSPACE_CSS=PASS"

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
for marker in 'amt-quick-actions-title' 'amt-quick-actions-grid' 'amt-quick-actions-track' 'data-amt-quick-actions-motion' 'translate3d(' 'Sales Invoice'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_QUICK_ACTIONS_JS=FAIL:MISSING_MARKER:$marker"
    exit 20
  fi
done
echo "BUILT_QUICK_ACTIONS_MOTION=PASS"
if ! grep -Fq 'nds-warehouse-workspace' "$LOCAL_JS_ASSET"; then
  echo "BUILT_WAREHOUSE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-warehouse-workspace"
  exit 28
fi
echo "BUILT_WAREHOUSE_WORKSPACE_JS=PASS"
if ! grep -Fq 'amt-accounts-workspace' "$LOCAL_JS_ASSET"; then
  echo "BUILT_ACCOUNTS_WORKSPACE_JS=FAIL:MISSING_MARKER:amt-accounts-workspace"
  exit 32
fi
echo "BUILT_ACCOUNTS_WORKSPACE_JS=PASS"
if ! grep -Fq 'nds-sales-workspace-redesign' "$LOCAL_JS_ASSET"; then
  echo "BUILT_SALES_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-sales-workspace-redesign"
  exit 36
fi
echo "BUILT_SALES_WORKSPACE_JS=PASS"
if ! grep -Fq 'nds-purchase-workspace-redesign' "$LOCAL_JS_ASSET"; then
  echo "BUILT_PURCHASE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-purchase-workspace-redesign"
  exit 40
fi
echo "BUILT_PURCHASE_WORKSPACE_JS=PASS"
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
for marker in 'amt-quick-actions-title' 'amt-quick-actions-grid' 'amt-quick-actions-track' 'data-amt-quick-actions-motion' 'translate3d(' 'Sales Invoice'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_QUICK_ACTIONS_JS=FAIL:MISSING_MARKER:$marker"
    exit 22
  fi
done
echo "SERVED_QUICK_ACTIONS_MOTION=PASS"
if ! grep -Fq 'nds-warehouse-workspace' "$SERVED_JS"; then
  echo "SERVED_WAREHOUSE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-warehouse-workspace"
  exit 29
fi
echo "SERVED_WAREHOUSE_WORKSPACE_JS=PASS"
if ! grep -Fq 'amt-accounts-workspace' "$SERVED_JS"; then
  echo "SERVED_ACCOUNTS_WORKSPACE_JS=FAIL:MISSING_MARKER:amt-accounts-workspace"
  exit 33
fi
echo "SERVED_ACCOUNTS_WORKSPACE_JS=PASS"
if ! grep -Fq 'nds-sales-workspace-redesign' "$SERVED_JS"; then
  echo "SERVED_SALES_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-sales-workspace-redesign"
  exit 37
fi
echo "SERVED_SALES_WORKSPACE_JS=PASS"
if ! grep -Fq 'nds-purchase-workspace-redesign' "$SERVED_JS"; then
  echo "SERVED_PURCHASE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-purchase-workspace-redesign"
  exit 41
fi
echo "SERVED_PURCHASE_WORKSPACE_JS=PASS"
if [ "$(sha256sum "$LOCAL_JS_ASSET" | awk '{print $1}')" != "$(sha256sum "$SERVED_JS" | awk '{print $1}')" ]; then
  echo "SERVED_QUICK_ACTIONS_JS=FAIL:HASH_MISMATCH"
  exit 23
fi
echo "BUILT_QUICK_ACTIONS_JS=PASS"
echo "SERVED_QUICK_ACTIONS_JS=PASS"
echo "SERVED_QUICK_ACTIONS_JS_MATCH=PASS"
echo "HEADER_RUNTIME_VERIFICATION=PASS"
echo "QUICK_ACTIONS_RUNTIME_ASSETS=PASS"
echo "WAREHOUSE_WORKSPACE_RUNTIME_ASSETS=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "CORE_MODIFICATION=NO"
