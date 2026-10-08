#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
INTERVAL="${RUNTIME_SYNC_INTERVAL:-5}"

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"


verify_amir_source() {
  test -s "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'app_include_css = "amir_theme.bundle.css"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'app_include_js = "amir_theme.bundle.js"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'web_include_css = "login_brand.bundle.css"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'web_include_js = "login_brand.bundle.js"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  echo "AMIR_THEME_SOURCE=PASS"
}

verify_amir_assets() {
  "$ROOT/env/bin/python" - <<'PY'
from pathlib import Path
import hashlib
import json

root = Path("/workspaces/ndserp-sa")
assets_path = root / "sites" / "assets" / "assets.json"
if not assets_path.is_file():
    raise SystemExit(f"ASSET_VERIFY=FAIL:{assets_path}")

assets = json.loads(assets_path.read_text(encoding="utf-8"))
required = (
    "amir_theme.bundle.css",
    "amir_theme.bundle.js",
    "login_brand.bundle.css",
    "login_brand.bundle.js",
)

for key in required:
    rel = assets.get(key)
    if not isinstance(rel, str) or not rel:
        raise SystemExit(f"ASSET_VERIFY=FAIL:MISSING_MAPPING:{key}")
    target = root / rel.lstrip("/")
    if not target.is_file():
        raise SystemExit(f"ASSET_VERIFY=FAIL:MISSING_FILE:{key}:{target}")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"ASSET_VERIFIED={key}")
    print(f"ASSET_PATH={rel}")
    print(f"ASSET_SHA256={digest}")

print("ASSET_SERVE_TREE=PASS")
PY
}

ensure_amir_theme_site_app() {
  verify_amir_source

  local installed_apps
  if ! installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null)"; then
    echo "SITE_APP_QUERY=FAIL"
    echo "SAFE_BOUNDARY=STOP_BEFORE_SITE_WRITE"
    return 21
  fi

  if printf '%s\n' "$installed_apps" | grep -q '^Amir Theme'; then
    echo "AMIR_THEME_SITE_APP=PASS"
    echo "AMIR_THEME_SITE_DB_WRITE=NO"
    return 0
  fi

  echo "AMIR_THEME_SITE_APP=MISSING_INSTALLING"
  echo "AMIR_THEME_SITE_DB_WRITE=THEME_APP_INSTALL_ONLY"
  bench --site "$SITE" install-app amir_theme_v16

  if ! installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null)"; then
    echo "SITE_APP_QUERY=FAIL_AFTER_INSTALL"
    return 22
  fi

  if printf '%s\n' "$installed_apps" | grep -q '^Amir Theme'; then
    echo "AMIR_THEME_SITE_APP=PASS_AFTER_INSTALL"
    return 0
  fi

  echo "AMIR_THEME_SITE_APP=FAIL_AFTER_INSTALL"
  return 23
}

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

  local current remote source_marker needs_build
  current="$(git rev-parse HEAD)"
  remote="$(git rev-parse origin/main)"

  echo "CODESPACE_HEAD=$current"
  echo "GITHUB_MAIN=$remote"

  if [ "$current" != "$remote" ]; then
    if is_dirty; then
      echo "SOURCE_SYNC=BLOCKED_DIRTY_WORKTREE"
      git status --short
      return 0
    fi

    git switch main
    git pull --ff-only origin main

    current="$(git rev-parse HEAD)"
    echo "SOURCE_SYNC=PASS"
    echo "SOURCE_HEAD=$current"

    # Re-exec the freshly pulled script so the active worker uses the current GitHub source immediately.
    if [ "${RUNTIME_SYNC_REEXEC:-0}" != "1" ]; then
      export RUNTIME_SYNC_REEXEC=1
      exec bash "$ROOT/codespace-runtime-sync.sh"
    fi
  else
    echo "SOURCE_SYNC=ALREADY_CURRENT"
  fi

  echo "=== VERIFY/INSTALL AMIR THEME ON SITE ==="
  if ! ensure_amir_theme_site_app; then
    echo "AMIR_THEME_SITE_APP=FAIL"
    return 24
  fi

  # Keep the Bench app registry aligned with the GitHub source tree after every source sync.
  cp bench/apps.txt sites/apps.txt
  echo "BENCH_APPS_REGISTRY=SYNCED"

  source_marker=""
  if [ -f "sites/.nds-runtime-source-head" ]; then
    source_marker="$(cat sites/.nds-runtime-source-head)"
  fi

  needs_build=0
  if [ "$source_marker" != "$current" ]; then
    needs_build=1
  elif ! verify_amir_assets >/dev/null 2>&1; then
    # A stale/missing asset tree forces a rebuild even when the Git SHA is unchanged.
    needs_build=1
    echo "ASSET_FRESHNESS=STALE_OR_MISSING"
  fi

  if [ "$needs_build" -eq 1 ]; then
    echo "=== BUILD CURRENT AMIR THEME ASSETS ==="
    bench build --app amir_theme_v16 --production
    bash apps/amir_theme_v16/scripts/harden_assets.sh
    bench --site "$SITE" clear-cache >/dev/null 2>&1 || true
    verify_amir_assets

    mkdir -p sites
    printf '%s\n' "$current" > sites/.nds-runtime-source-head

    echo "ASSET_BUILD=PASS"
    echo "SERVED_SOURCE_HEAD=$(cat sites/.nds-runtime-source-head)"
  else
    echo "ASSET_BUILD=ALREADY_CURRENT"
    verify_amir_assets
  fi

  echo "CORE_MODIFICATION=NO"
  echo "MIGRATION=NO"
  echo "DB_WRITE=NO_AFTER_THEME_ACTIVATION"
}


if [ "${1:-}" = "--once" ]; then
  sync_once
  exit 0
fi

while true; do
  sync_once || echo "SOURCE_SYNC=ERROR_RETRY"
  sleep "$INTERVAL"
done
