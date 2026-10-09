#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
PID_FILE="$ROOT/logs/codespace-runtime-sync.pid"
SYNC_LOG="$ROOT/logs/codespace-runtime-sync.log"

cd "$ROOT"
mkdir -p logs

echo "=== NDS ERP SAUDI — POST-START RUNTIME ACTIVATION ==="
echo "ROOT=$ROOT"

sudo service mariadb start

# First sync source, clean database-only custom reports backup-first, and build assets.
bash "$ROOT/codespace-runtime-sync.sh" --once

# Never restart or validate an outdated/dirty checkout as if it were current.
git fetch origin main
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
if [ ! -s "$ROOT/sites/.nds-custom-report-cleanup-v1" ]; then
  echo "CUSTOM_REPORT_CLEANUP=FAIL_MARKER_MISSING"
  exit 32
fi

# Restart the local Bench process so Python Hooks/modules are imported from current HEAD.
NDS_FORCE_BENCH_RESTART=1 bash "$ROOT/codespace-start-server.sh"

# Verify the assets actually served after the new Frappe process is ready.
bash "$ROOT/codespace-verify-runtime.sh"
printf '%s\n' "$(git rev-parse HEAD)" > "$ROOT/sites/.nds-runtime-served-head"
echo "SERVED_RUNTIME_HEAD=$(cat "$ROOT/sites/.nds-runtime-served-head")"

# Keep GitHub main synchronized while the Codespace remains open. The sync worker
# restarts Bench after source/asset updates and writes a single auditable log.
if [ -s "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    old_cmd="$(tr '\0' ' ' < "/proc/$old_pid/cmdline" 2>/dev/null || true)"
    if [[ "$old_cmd" == *"codespace-runtime-sync.sh"* ]]; then
      echo "RUNTIME_SYNC_DAEMON=ALREADY_RUNNING"
      echo "RUNTIME_SYNC_PID=$old_pid"
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
echo "DB_WRITE_POLICY=BACKUP_FIRST_LOCAL_ONLY"
echo "PRODUCTION_DB_WRITE=NO"
echo "EGYPT_ERP_MODIFICATION=NO"
echo "CORE_MODIFICATION=NO"
echo "SSH/WSL session remains open — no logout / no exit."
