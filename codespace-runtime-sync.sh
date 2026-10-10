#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
INTERVAL="${RUNTIME_SYNC_INTERVAL:-5}"
SYNC_MODE="${NDS_RUNTIME_SYNC_ORIGIN_MODE:-${1:-loop}}"

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# Serialize all sync/build cycles across postStart, a manual --once run, and
# the background worker. Frappe's bench_build lock remains authoritative.
if [ "${NDS_RUNTIME_SYNC_LOCK_HELD:-0}" != "1" ]; then
  mkdir -p "$ROOT/config" "$ROOT/logs"
  RUNTIME_LOCK="/tmp/ndserp-sa-runtime-sync.lock"
  LOCK_WAIT="${NDS_RUNTIME_SYNC_LOCK_WAIT:-900}"

  if [ "${1:-}" = "--once" ]; then
    exec flock -w "$LOCK_WAIT" -o "$RUNTIME_LOCK" \
      env NDS_RUNTIME_SYNC_LOCK_HELD=1 \
          NDS_RUNTIME_SYNC_ORIGIN_MODE="--once" \
      bash "$ROOT/codespace-runtime-sync.sh" --once
  fi

  while true; do
    if ! flock -w "$LOCK_WAIT" -o "$RUNTIME_LOCK" \
      env NDS_RUNTIME_SYNC_LOCK_HELD=1 \
          NDS_RUNTIME_SYNC_ORIGIN_MODE="loop" \
      bash "$ROOT/codespace-runtime-sync.sh" --once; then
      echo "RUNTIME_SYNC_CYCLE=FAIL"
    fi
    sleep "$INTERVAL"
  done
fi


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
import re

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
    # Prefer the exact Frappe public asset tree that serves browser requests.
    site_target = root / "sites" / rel.lstrip("/")
    target = site_target if site_target.is_file() else root / rel.lstrip("/")
    if not target.is_file():
        raise SystemExit(f"ASSET_VERIFY=FAIL:MISSING_FILE:{key}:{target}")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"ASSET_VERIFIED={key}")
    print(f"ASSET_PATH={rel}")
    print(f"ASSET_SHA256={digest}")
    if key == "amir_theme.bundle.css":
        css = target.read_text(encoding="utf-8").lower()
        css_compact = "".join(css.split())
        required_header_markers = ("body .navbar", "58px", "#0a2342")
        missing = [marker for marker in required_header_markers if marker not in css]
        if missing:
            raise SystemExit(
                "MODERN_HEADER_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        required_quick_actions_css = (
            ".amt-quick-actions",
            ".amt-quick-actions-grid",
            ".amt-quick-action-arrow",
            ".amt-quick-actions-track",
            "height:104px",
            "min-height:104px",
            "width:36px",
            "width:20px",
            "margin-top:auto",
            "background:#eef1f4",
            "display:none!important",
        )
        missing = [marker for marker in required_quick_actions_css if marker not in css_compact]
        if missing:
            raise SystemExit(
                "QUICK_ACTIONS_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("MODERN_HEADER_CSS=PASS")
        print("QUICK_ACTIONS_CSS=PASS")
        required_warehouse_css = (
            ".nds-warehouse-workspace",
            "border-block-start:3pxsolid#0a2342",
        )
        missing = [marker for marker in required_warehouse_css if marker not in css_compact]
        if missing:
            raise SystemExit(
                "WAREHOUSE_WORKSPACE_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("WAREHOUSE_WORKSPACE_CSS=PASS")
        required_accounts_css = (
            ".amt-accounts-workspace",
            ".codex-editor__redactor",
            "grid-template-columns:repeat(12,minmax(0,1fr))",
            "#bd5548",
            ".nds-accounts-dashboard",
            ".nds-accounts-kpi-grid",
            ".nds-accounts-expenses-chart",
            ".nds-accounts-revenue-chart",
            ".nds-accounts-invoice-table",
            "grid-template-columns:repeat(4,minmax(0,1fr))",
        )
        missing = [marker for marker in required_accounts_css if marker not in css_compact]
        if missing:
            raise SystemExit(
                "ACCOUNTS_WORKSPACE_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("ACCOUNTS_WORKSPACE_CSS=PASS")
        required_sales_workspace_css = (
            ".nds-sales-workspace-redesign",
            "#page-workspaces",
            ".page-head",
            "#d4af37",
            ".nds-sales-dashboard",
            ".nds-sales-kpi-grid",
            ".nds-sales-revenue-chart",
            ".nds-sales-channels-chart",
            ".nds-sales-invoices",
            "grid-template-columns:repeat(4,minmax(0,1fr))",
        )
        missing = [marker for marker in required_sales_workspace_css if marker not in css_compact]
        if missing:
            raise SystemExit(
                "SALES_WORKSPACE_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("SALES_WORKSPACE_CSS=PASS")
        required_purchase_workspace_css = (
            ".nds-purchase-workspace-redesign",
            "#page-workspaces",
            ".codex-editor__redactor",
            "grid-template-columns:repeat(12,minmax(0,1fr))",
            "#c58b3c",
            "grid-column:span7",
            "grid-column:span5",
            "border-collapse:separate",
        )
        missing = [marker for marker in required_purchase_workspace_css if marker not in css_compact]
        if missing:
            raise SystemExit(
                "PURCHASE_WORKSPACE_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("PURCHASE_WORKSPACE_CSS=PASS")
    elif key == "amir_theme.bundle.js":
        js = target.read_text(encoding="utf-8")
        # Use stable ASCII markers: production bundling may Unicode-escape Arabic literals.
        required_quick_actions_js = (
            "amt-quick-actions-title",
            "amt-quick-actions-grid",
            "amt-quick-actions-track",
            "data-amt-quick-actions-motion",
            "data-amt-quick-actions-loop",
            "amt-quick-action-clone",
            "translate3d(",
            "Sales Invoice",
        )
        missing = [marker for marker in required_quick_actions_js if marker not in js]
        if missing:
            raise SystemExit(
                "QUICK_ACTIONS_JS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("QUICK_ACTIONS_JS=PASS")
        if "nds-warehouse-workspace" not in js:
            raise SystemExit("WAREHOUSE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-warehouse-workspace")
        print("WAREHOUSE_WORKSPACE_JS=PASS")
        required_accounts_js = (
            "amt-accounts-workspace",
            "nds-accounts-dashboard",
            "nds-accounts-kpi-grid",
            "nds-accounts-invoice-table",
            "Accounts Dashboard",
        )
        missing = [marker for marker in required_accounts_js if marker not in js]
        if missing:
            raise SystemExit(
                "ACCOUNTS_WORKSPACE_JS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("ACCOUNTS_WORKSPACE_JS=PASS")
        required_sales_workspace_js = (
            "nds-sales-workspace-redesign",
            "nds-sales-dashboard",
            "nds-sales-revenue-chart",
            "nds-sales-channels-chart",
            "nds-sales-invoices",
        )
        missing = [marker for marker in required_sales_workspace_js if marker not in js]
        if missing:
            raise SystemExit(
                "SALES_WORKSPACE_JS=FAIL:MISSING_MARKERS:" + ",".join(missing)
            )
        print("SALES_WORKSPACE_JS=PASS")
        if "nds-purchase-workspace-redesign" not in js:
            raise SystemExit("PURCHASE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-purchase-workspace-redesign")
        print("PURCHASE_WORKSPACE_JS=PASS")

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

  if printf '%s\n' "$installed_apps" | grep -Eq '^(Amir Theme|amir_theme_v16)([[:space:]]|$)'; then
    echo "AMIR_THEME_SITE_APP=PASS"
    echo "AMIR_THEME_SITE_DB_WRITE=NO"
    return 0
  fi

  echo "AMIR_THEME_SITE_APP=MISSING"
  echo "AMIR_THEME_SITE_DB_WRITE=BLOCKED"
  echo "SAFE_BOUNDARY=STOP_BEFORE_SITE_WRITE"
  return 24
}


run_asset_build_with_lock_retry() {
  local attempt=1
  local max_attempts="${NDS_BUILD_LOCK_RETRIES:-30}"
  local delay="${NDS_BUILD_LOCK_RETRY_DELAY:-10}"
  local log_file rc

  log_file="$(mktemp "${TMPDIR:-/tmp}/nds-bench-build.XXXXXX")"
  while [ "$attempt" -le "$max_attempts" ]; do
    echo "ASSET_BUILD_ATTEMPT=$attempt/$max_attempts"
    if bench build --app amir_theme_v16 --production >"$log_file" 2>&1; then
      cat "$log_file"
      rm -f "$log_file"
      echo "ASSET_BUILD_COMMAND=PASS"
      return 0
    else
      rc=$?
    fi

    cat "$log_file"
    if grep -Eqi 'LockTimeoutError|Failed to a[c]?quire lock: bench_build|bench_build\.lock.*could not be acquired' "$log_file"; then
      if [ "$attempt" -lt "$max_attempts" ]; then
        echo "ASSET_BUILD_LOCK=BUSY"
        echo "ASSET_BUILD_RETRY_IN=${delay}s"
        sleep "$delay"
        attempt=$((attempt + 1))
        continue
      fi
      echo "ASSET_BUILD_LOCK=TIMEOUT"
    fi

    rm -f "$log_file"
    echo "ASSET_BUILD_COMMAND=FAIL"
    return "$rc"
  done

  rm -f "$log_file"
  echo "ASSET_BUILD_COMMAND=FAIL"
  return 1
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

  local current remote source_marker served_marker needs_build
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

    # GitHub main is the sole source of truth for this Saudi Codespace.
    # A clean ahead/diverged checkout must never survive as a runtime source.
    if git merge-base --is-ancestor "$current" "$remote"; then
      git pull --ff-only origin main
    else
      echo "SOURCE_SYNC=RESET_TO_GITHUB_MAIN"
      git reset --hard "$remote"
    fi

    current="$(git rev-parse HEAD)"
    echo "SOURCE_SYNC=PASS"
    echo "SOURCE_HEAD=$current"

    # Re-exec the freshly synced script so the active worker uses current GitHub source immediately.
    if [ "${RUNTIME_SYNC_REEXEC:-0}" != "1" ]; then
      export RUNTIME_SYNC_REEXEC=1
      # A locked worker remains a single cycle after a source refresh.
      if [ "${NDS_RUNTIME_SYNC_LOCK_HELD:-0}" = "1" ] || [ "$SYNC_MODE" = "--once" ]; then
        exec bash "$ROOT/codespace-runtime-sync.sh" --once
      fi
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
  served_marker=""
  if [ -f "sites/.nds-runtime-served-head" ]; then
    served_marker="$(cat sites/.nds-runtime-served-head)"
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
    run_asset_build_with_lock_retry
    bash apps/amir_theme_v16/scripts/harden_assets.sh
    bench --site "$SITE" clear-cache >/dev/null 2>&1 || true
    verify_amir_assets

    mkdir -p sites
    printf '%s\n' "$current" > sites/.nds-runtime-source-head

    echo "ASSET_BUILD=PASS"
    echo "BUILT_SOURCE_HEAD=$(cat sites/.nds-runtime-source-head)"
    if curl --connect-timeout 1 --max-time 2 -fsS -o /dev/null "http://127.0.0.1:8080/login"; then
      if [ "$SYNC_MODE" = "--once" ]; then
        # One-shot UI application restarts and verifies the local server in
        # codespace-apply-quick-actions-ui.sh; skip pre-refresh verification.
        echo "SERVED_ASSET_REFRESH=DEFERRED_TO_APPLY_SCRIPT"
      else
        NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"
        bash "$ROOT/codespace-verify-runtime.sh"
        printf '%s\\n' "$current" > sites/.nds-runtime-served-head
        echo "SERVED_ASSET_REFRESH=PASS"
      fi
    else
      echo "SERVED_ASSET_REFRESH=DEFERRED_SERVER_NOT_READY"
    fi
  else
    echo "ASSET_BUILD=ALREADY_CURRENT"
    verify_amir_assets
    if [ "$served_marker" != "$current" ] && [ "$SYNC_MODE" != "--once" ] && curl --connect-timeout 1 --max-time 2 -fsS -o /dev/null "http://127.0.0.1:8080/login"; then
      echo "SERVED_ASSET_REFRESH=RETRY"
      NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"
      bash "$ROOT/codespace-verify-runtime.sh"
      printf '%s\n' "$current" > sites/.nds-runtime-served-head
      echo "SERVED_ASSET_REFRESH=PASS"
    fi
  fi

  # Database cleanup is deliberately opt-in and runs only after the UI assets
  # have been built and served-asset verification has completed. A linked Report
  # must never block unrelated CSS/JS deployment or trigger backups on every sync.
  if [ "${NDS_CLEANUP_CUSTOM_REPORTS:-0}" = "1" ]; then
    if [ -s "$ROOT/sites/.nds-custom-report-cleanup-v1" ]; then
      echo "CUSTOM_REPORT_POLICY=ALREADY_APPLIED"
    elif bash "$ROOT/codespace-remove-custom-reports-safe.sh"; then
      echo "CUSTOM_REPORT_CLEANUP=PASS"
    else
      echo "CUSTOM_REPORT_CLEANUP=FAIL_NONBLOCKING_UI_BUILD"
    fi
  else
    echo "CUSTOM_REPORT_CLEANUP=SKIPPED_UI_SYNC_ONLY"
  fi

  echo "CORE_MODIFICATION=NO"
  echo "MIGRATION=NO"
  echo "DB_WRITE_POLICY=BACKUP_FIRST_LOCAL_ONLY"
  echo "PRODUCTION_DB_WRITE=NO"
}


if [ "${1:-}" = "--once" ]; then
  sync_once
  exit 0
fi

while true; do
  sync_once || echo "SOURCE_SYNC=ERROR_RETRY"
  sleep "$INTERVAL"
done
