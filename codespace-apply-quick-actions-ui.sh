#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
APPLY_LOCK="/tmp/ndserp-sa-ui-apply.lock"
PID_FILE="$ROOT/logs/codespace-runtime-sync.pid"
SYNC_LOG="$ROOT/logs/codespace-runtime-sync.log"

cd "$ROOT"
mkdir -p config logs

# Hold a single deployment lock for quiesce -> build -> restart -> HTTP verify.
# -o prevents the detached background worker from inheriting the lock descriptor.
if [ "${NDS_UI_APPLY_LOCKED:-0}" != "1" ]; then
  exec flock -w "${NDS_UI_APPLY_LOCK_WAIT:-1200}" -o "$APPLY_LOCK" \
    env NDS_UI_APPLY_LOCKED=1 bash "$ROOT/codespace-apply-quick-actions-ui.sh" "$@"
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "=== NDS ERP SAUDI — APPLY QUICK ACTIONS UI TO RUNTIME ==="
echo "ROOT=$ROOT"
echo "SITE=$SITE"
echo "PORT=8080"

is_dirty() {
  ! git diff --quiet ||
  ! git diff --cached --quiet ||
  [ -n "$(git ls-files --others --exclude-standard)" ]
}

git fetch origin main
current="$(git rev-parse HEAD)"
remote="$(git rev-parse origin/main)"
echo "CODESPACE_HEAD=$current"
echo "GITHUB_MAIN=$remote"

if [ "$current" != "$remote" ]; then
  if is_dirty; then
    echo "SOURCE_SYNC=BLOCKED_DIRTY_WORKTREE"
    git status --short
    echo "SAFE_BOUNDARY=NO_RESET_OF_LOCAL_CHANGES"
    exit 20
  fi
  git switch main
  if git merge-base --is-ancestor "$current" "$remote"; then
    git pull --ff-only origin main
  else
    echo "SOURCE_SYNC=RESET_TO_GITHUB_MAIN"
    git reset --hard "$remote"
  fi
  echo "SOURCE_SYNC=PASS"
  # Re-enter the updated copy of this script after source synchronization.
  exec bash "$ROOT/codespace-apply-quick-actions-ui.sh" "$@"
fi

echo "SOURCE_SYNC=ALREADY_CURRENT"

# Stop only the project's own sync worker, and wait for any in-flight build to
# finish naturally. This never kills bench build and never deletes its lock file.
bash "$ROOT/codespace-quiesce-runtime-sync.sh"

# Ensure the local Codespace DB service is available for read-only site checks.
sudo service mariadb start

# This one-shot builds and verifies the current sources; serving verification is
# intentionally deferred until the local Bench server has reloaded its manifest.
NDS_BUILD_LOCK_RETRIES="${NDS_BUILD_LOCK_RETRIES:-30}" \
  bash "$ROOT/codespace-runtime-sync.sh" --once

# Refresh the local Codespace process so it loads the just-built asset manifest.
NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"

# Hash-compare the exact CSS and JS downloaded over HTTP against the built files.
bash "$ROOT/codespace-verify-runtime.sh"
printf '%s\n' "$(git rev-parse HEAD)" > "$ROOT/sites/.nds-runtime-served-head"
echo "SERVED_RUNTIME_HEAD=$(cat "$ROOT/sites/.nds-runtime-served-head")"
echo "QUICK_ACTIONS_RUNTIME_ASSETS=PASS"
echo "VISIBLE_UPDATE_READY=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "PRODUCTION_DB_WRITE=NO"
echo "CORE_MODIFICATION=NO"
echo "EGYPT_ERP_MODIFICATION=NO"

# Restore the ongoing source watcher only after the runtime passed HTTP checks.
nohup env RUNTIME_SYNC_INTERVAL=10 bash "$ROOT/codespace-runtime-sync.sh" \
  >> "$SYNC_LOG" 2>&1 < /dev/null &
sync_pid=$!
printf '%s\n' "$sync_pid" > "$PID_FILE"
sleep 1
if ! kill -0 "$sync_pid" 2>/dev/null; then
  echo "RUNTIME_SYNC_DAEMON=FAIL"
  tail -n 80 "$SYNC_LOG" 2>/dev/null || true
  exit 50
fi

echo "RUNTIME_SYNC_DAEMON=STARTED"
echo "RUNTIME_SYNC_PID=$sync_pid"
echo "RUNTIME_SYNC_LOG=$SYNC_LOG"
echo "NEXT=Open Desktop and press Ctrl+Shift+R"
echo "SSH session remains open — no logout / no exit."
