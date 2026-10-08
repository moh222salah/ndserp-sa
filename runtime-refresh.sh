#!/usr/bin/env bash
set -Eeuo pipefail

# Resolve the active NDS ERP Saudi checkout instead of hard-coding Codespaces.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  ROOT="/home/moh222salah/projects/nds/ndserp-sa"
fi
SITE="ndserpsa.nds-sa.com"
PORT="8080"

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "=== NDS ERP SAUDI — RUNTIME REFRESH ==="
echo "SOURCE=GitHub main"
echo "ROOT=$ROOT"
echo "SITE=$SITE"

# Preserve unrelated local work. Only block when files owned by this refresh
# would conflict with the incoming main branch state.
BLOCKED_FILES=""
while IFS= read -r path; do
  case "$path" in
    apps/amir_theme_v16/amir_theme_v16/src/scss/login_brand.bundle.scss|apps/amir_theme_v16/amir_theme_v16/src/js/core/login_brand.js|runtime-refresh.sh)
      BLOCKED_FILES="\${BLOCKED_FILES}\${path}"$'\n'
      ;;
  esac
done < <(
  {
    git diff --name-only
    git diff --cached --name-only
    git ls-files --others --exclude-standard
  } | sort -u
)

if [ -n "$BLOCKED_FILES" ]; then
  echo "RUNTIME_REFRESH=BLOCKED_TARGET_DIRTY"
  printf '%s' "$BLOCKED_FILES"
  exit 2
fi

if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "UNRELATED_LOCAL_CHANGES=PRESERVED"
  git status --short
fi

git fetch origin main
git switch main
git pull --ff-only origin main

echo "SOURCE_HEAD=$(git rev-parse HEAD)"
echo "SOURCE_HEAD_SHORT=$(git rev-parse --short HEAD)"

echo "=== BUILD AMIR THEME ==="
bench build --app amir_theme_v16 --production
bash apps/amir_theme_v16/scripts/harden_assets.sh

ASSET_ROOT="$ROOT/apps/amir_theme_v16/amir_theme_v16/public/dist"
if grep -RIl --exclude="*.map" "amt-lb-language" "$ASSET_ROOT" >/dev/null 2>&1; then
  echo "LOGIN_ASSET_CODE=PASS"
else
  echo "LOGIN_ASSET_CODE=FAIL"
  exit 3
fi

# Cache clear only; no schema migration and no database data mutation.
# A site-cache failure must not prevent verification of the already-built
# static login assets.
if bench --site "$SITE" clear-cache; then
  echo "CACHE_CLEAR=PASS"
else
  echo "CACHE_CLEAR=SKIPPED"
fi

LOGIN_HTML="/tmp/nds_runtime_refresh_login.html"
if curl -fsS "http://127.0.0.1:${PORT}/login" -o "$LOGIN_HTML"; then
  echo "LOGIN_PAGE_FETCH=PASS"
else
  echo "LOGIN_PAGE_FETCH=FAIL"
  exit 4
fi

LOGIN_CSS_PATH="$(
  grep -oE '/assets/[^"]*login_brand[^"]*\.css' "$LOGIN_HTML" |
  sort -u |
  head -1
)"

if [ -z "$LOGIN_CSS_PATH" ]; then
  echo "RESPONSIVE_CSS_SERVED=FAIL"
  echo "LOGIN_CSS_PATH=NOT_FOUND"
  exit 5
fi

echo "LOGIN_CSS_PATH=$LOGIN_CSS_PATH"
LOGIN_CSS_FILE="/tmp/nds_runtime_refresh_login.css"
curl -fsS "http://127.0.0.1:${PORT}\${LOGIN_CSS_PATH}" -o "$LOGIN_CSS_FILE"

if grep -q 'amt-lb-split' "$LOGIN_CSS_FILE" &&
   grep -q '100svh' "$LOGIN_CSS_FILE" &&
   grep -q '100dvh' "$LOGIN_CSS_FILE" &&
   grep -q 'max-width:560px' "$LOGIN_CSS_FILE"; then
  echo "RESPONSIVE_CSS_SERVED=PASS"
else
  echo "RESPONSIVE_CSS_SERVED=FAIL"
  exit 6
fi

if grep -q 'margin-top:0' "$LOGIN_CSS_FILE" &&
   grep -q 'padding-top:0' "$LOGIN_CSS_FILE" &&
   grep -q 'page-content-wrapper' "$LOGIN_CSS_FILE" &&
   grep -q '100dvh' "$LOGIN_CSS_FILE" &&
   grep -q 'body:has(.for-login)' "$LOGIN_CSS_FILE"; then
  echo "TOP_GAP_CSS_SERVED=PASS"
else
  echo "TOP_GAP_CSS_SERVED=FAIL"
  exit 7
fi

if grep -q 'amt-lb-language' "$LOGIN_HTML"; then
  echo "LOGIN_LANGUAGE_MARKUP_REFERENCE=PASS"
elif grep -q '/assets/amir_theme_v16/dist/js/login_brand.bundle' "$LOGIN_HTML"; then
  echo "LOGIN_LANGUAGE_MARKUP_REFERENCE=PASS_JS_INJECTION"
else
  echo "LOGIN_LANGUAGE_MARKUP_REFERENCE=FAIL"
  exit 8
fi

if grep -q 'border-radius:30px' "$LOGIN_CSS_FILE" &&
   grep -q 'border-radius:24px' "$LOGIN_CSS_FILE"; then
  echo "BRAND_IMAGE_FRAME_ROUNDED=PASS"
else
  echo "BRAND_IMAGE_FRAME_ROUNDED=FAIL"
  exit 10
fi

if curl -fsS -o /dev/null -w "LOGIN_HTTP=%{http_code}\n" "http://127.0.0.1:${PORT}/login"; then
  echo "LOGIN_HTTP=PASS"
else
  echo "LOGIN_HTTP=FAIL_OR_SERVICE_NOT_RUNNING"
  exit 9
fi

echo "UI/CSS=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "PRODUCTION_DB_WRITE=NO"
echo "RESTART=NO"
echo "EGYPTIAN_ERP=UNTOUCHED"
echo "SSH/WSL session remains open — no logout / no exit."
