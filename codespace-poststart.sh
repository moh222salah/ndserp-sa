#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
PID_FILE="$ROOT/logs/codespace-runtime-sync.pid"
SYNC_LOG="$ROOT/logs/codespace-runtime-sync.log"

cd "$ROOT"
mkdir -p logs config

# Serialize Codespace postStart with manual UI application so they cannot
# build assets or restart the local Bench server at the same time.
if [ "${NDS_UI_APPLY_LOCKED:-0}" != "1" ]; then
  exec flock -w "${NDS_UI_APPLY_LOCK_WAIT:-1200}" -o "/tmp/ndserp-sa-ui-apply.lock" \
    env NDS_UI_APPLY_LOCKED=1 bash "$ROOT/codespace-poststart.sh"
fi

echo "=== NDS ERP SAUDI — POST-START RUNTIME ACTIVATION ==="
echo "ROOT=$ROOT"

# Keep source-to-runtime synchronization alive even if a one-shot build or
# served-asset check fails. The loop retries safely; it never migrates or writes DB.
runtime_sync_worker_is_running() {
  local pid cmd cwd
  [ -s "$PID_FILE" ] || return 1
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  [[ "$cmd" == *"$ROOT/codespace-runtime-sync.sh"* && "$cwd" == "$ROOT" ]]
}

ensure_runtime_sync_worker_on_exit() {
  local rc=$?
  trap - EXIT
  if ! runtime_sync_worker_is_running; then
    echo "RUNTIME_SYNC_RECOVERY=STARTING_AFTER_POSTSTART_EXIT exit=$rc" >> "$SYNC_LOG"
    nohup env RUNTIME_SYNC_INTERVAL=10 bash "$ROOT/codespace-runtime-sync.sh" \
      >> "$SYNC_LOG" 2>&1 < /dev/null &
    local recovered_pid=$!
    printf '%s\n' "$recovered_pid" > "$PID_FILE"
    sleep 1
    if kill -0 "$recovered_pid" 2>/dev/null; then
      echo "RUNTIME_SYNC_RECOVERY=STARTED pid=$recovered_pid" >> "$SYNC_LOG"
    else
      echo "RUNTIME_SYNC_RECOVERY=FAIL pid=$recovered_pid" >> "$SYNC_LOG"
    fi
  fi
  exit "$rc"
}
trap ensure_runtime_sync_worker_on_exit EXIT

sudo service mariadb start

# Stop a previous worker before the startup build; wait for any child build to
# release Frappe's real lock naturally. Never delete bench_build.lock.
bash "$ROOT/codespace-quiesce-runtime-sync.sh"

# Synchronize source first, then stop the previous Bench tree before building.
# Tracked source is aligned to GitHub main; untracked runtime/site/log files are preserved.
git fetch origin main
branch="$(git branch --show-current)"
if [ "$branch" != "main" ]; then
  git switch --discard-changes -C main origin/main
elif [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ] ||
     ! git diff --quiet || ! git diff --cached --quiet; then
  git reset --hard origin/main
fi

SOURCE_HEAD="$(git rev-parse HEAD)"
GITHUB_MAIN="$(git rev-parse origin/main)"
echo "CODESPACE_HEAD=$SOURCE_HEAD"
echo "GITHUB_MAIN=$GITHUB_MAIN"
if [ "$SOURCE_HEAD" != "$GITHUB_MAIN" ]; then
  echo "SOURCE_SYNC=FAIL_HEAD_MISMATCH"
  git status --short
  echo "BENCH_RESTART=BLOCKED_STALE_SOURCE"
  exit 31
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "SOURCE_SYNC=FAIL_TRACKED_WORKTREE_DIRTY"
  git status --short
  exit 32
fi
echo "SOURCE_SYNC=PASS"

# Restart now so the updated Procfile takes effect and no old bench watch can race with a build.
NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"

# Compile only after the competing watcher has been removed from the runtime.
# Custom Reports cleanup remains separate and is never required for UI sync.
bash "$ROOT/codespace-runtime-sync.sh" --once

# Never serve a build made from an outdated checkout.
git fetch origin main
SOURCE_HEAD="$(git rev-parse HEAD)"
GITHUB_MAIN="$(git rev-parse origin/main)"
echo "BUILT_CODESPACE_HEAD=$SOURCE_HEAD"
echo "GITHUB_MAIN_AFTER_BUILD=$GITHUB_MAIN"
if [ "$SOURCE_HEAD" != "$GITHUB_MAIN" ]; then
  echo "SOURCE_SYNC=FAIL_HEAD_CHANGED_DURING_BUILD"
  echo "SAFE_BOUNDARY=NO_STALE_ASSET_RESTART"
  exit 33
fi
if [ -s "$ROOT/sites/.nds-custom-report-cleanup-v1" ]; then
  echo "CUSTOM_REPORT_CLEANUP=PASS"
else
  echo "CUSTOM_REPORT_CLEANUP=NOT_REQUIRED_FOR_UI_SYNC"
  echo "CUSTOM_REPORT_DB_WRITE=NO"
fi

# Reload the verified manifest and hooks from the completed build.
NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"

# Verify the assets actually served after the new Frappe process is ready.
bash "$ROOT/codespace-verify-runtime.sh"
printf '%s\n' "$(git rev-parse HEAD)" > "$ROOT/sites/.nds-runtime-served-head"
echo "SERVED_RUNTIME_HEAD=$(cat "$ROOT/sites/.nds-runtime-served-head")"

# Start an independent connection watchdog; a stale PID must not count as running.
if bash "$ROOT/codespace-connection-watchdog.sh" --start; then
  echo "CONNECTION_WATCHDOG=READY"
else
  echo "CONNECTION_WATCHDOG=START_FAILED_NONBLOCKING"
fi

# Keep GitHub main synchronized while the Codespace remains open. The sync worker
# watches source and asset hashes; it does not run database cleanup as part of UI sync.
if [ -s "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    old_cmd="$(tr '\0' ' ' < "/proc/$old_pid/cmdline" 2>/dev/null || true)"
    if [[ "$old_cmd" == *"codespace-runtime-sync.sh"* ]]; then
      echo "RUNTIME_SYNC_DAEMON=ALREADY_RUNNING"
      echo "RUNTIME_SYNC_PID=$old_pid"
      echo "DB_WRITE=NO"
      echo "MIGRATION=NO"
      echo "CORE_MODIFICATION=NO"
      echo "EGYPT_ERP_MODIFICATION=NO"
      echo "SSH/WSL session remains open — no logout / no exit."
      exit 0
    fi
  fi
fi

nohup env RUNTIME_SYNC_INTERVAL=10 bash "$ROOT/codespace-runtime-sync.sh" \
  >> "$SYNC_LOG" 2>&1 < /dev/null &
sync_pid=$!
printf '%s\n' "$sync_pid" > "$PID_FILE"
sleep 1
kill -0 "$sync_pid" 2>/dev/null
echo "RUNTIME_SYNC_DAEMON=STARTED"
echo "RUNTIME_SYNC_INTERVAL=10"
echo "RUNTIME_SYNC_PID=$sync_pid"
echo "RUNTIME_SYNC_LOG=$SYNC_LOG"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "PRODUCTION_DB_WRITE=NO"
echo "EGYPT_ERP_MODIFICATION=NO"
echo "CORE_MODIFICATION=NO"
echo "SSH/WSL session remains open — no logout / no exit."
