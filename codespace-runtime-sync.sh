#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
INTERVAL="${RUNTIME_SYNC_INTERVAL:-5}"

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "=== NDS ERP SAUDI — CODESPACE RUNTIME SYNC ==="
echo "ROOT=$ROOT"
echo "SITE=$SITE"
echo "INTERVAL=${INTERVAL}s"

is_dirty() {
  ! git diff --quiet ||
  ! git diff --cached --quiet ||
  [ -n "$(git ls-files --others --exclude-standard)" ]
}

sync_once() {
  git fetch origin main

  local current remote
  current="$(git rev-parse HEAD)"
  remote="$(git rev-parse origin/main)"

  echo "CODESPACE_HEAD=$current"
  echo "GITHUB_MAIN=$remote"

  if [ "$current" = "$remote" ]; then
    echo "SOURCE_SYNC=ALREADY_CURRENT"
    return 0
  fi

  if is_dirty; then
    echo "SOURCE_SYNC=BLOCKED_DIRTY_WORKTREE"
    git status --short
    return 0
  fi

  git switch main
  git pull --ff-only origin main

  echo "SOURCE_SYNC=PASS"
  echo "SOURCE_HEAD=$(git rev-parse HEAD)"

  echo "=== VERIFY AMIR THEME SITE APP ==="
  installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null || true)"
  if printf '%s\n' "$installed_apps" | grep -q '^Amir Theme'; then
    echo "AMIR_THEME_SITE_APP=PASS"
  elif [ -f "sites/.nds-site-provisioning-mode" ] && grep -qx "clean" "sites/.nds-site-provisioning-mode"; then
    bench --site "$SITE" install-app amir_theme_v16
    echo "AMIR_THEME_SITE_APP=INSTALLED"
  else
    echo "AMIR_THEME_SITE_APP=FAIL"
    echo "SAFE_BOUNDARY=REFUSE_DB_CHANGE_ON_EXISTING_SITE"
    return 22
  fi

  echo "=== BUILD CURRENT AMIR THEME ASSETS ==="
  bench build --app amir_theme_v16 --production
  bash apps/amir_theme_v16/scripts/harden_assets.sh
  bench --site "$SITE" clear-cache >/dev/null 2>&1 || true

  mkdir -p sites
  printf '%s\n' "$(git rev-parse HEAD)" > sites/.nds-runtime-source-head

  echo "ASSET_BUILD=PASS"
  echo "SERVED_SOURCE_HEAD=$(cat sites/.nds-runtime-source-head)"
  echo "DB_WRITE=NO"
  echo "MIGRATION=NO"
}

if [ "${1:-}" = "--once" ]; then
  sync_once
  exit 0
fi

while true; do
  sync_once || echo "SOURCE_SYNC=ERROR_RETRY"
  sleep "$INTERVAL"
done
