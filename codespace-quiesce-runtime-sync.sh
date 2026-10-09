#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
PID_FILE="$ROOT/logs/codespace-runtime-sync.pid"
cd "$ROOT"

runtime_sync_pids() {
  while IFS= read -r line; do
    local pid cmd cwd
    pid="${line%% *}"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    [[ -e "/proc/$pid/cwd" ]] || continue
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    if [[ "$cmd" == *"$ROOT/codespace-runtime-sync.sh"* && "$cwd" == "$ROOT" ]]; then
      printf '%s\n' "$pid"
    fi
  done < <(pgrep -af '[c]odespace-runtime-sync.sh' || true)
}

bench_build_pids() {
  while IFS= read -r line; do
    local pid cmd cwd
    pid="${line%% *}"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    [[ -e "/proc/$pid/cwd" ]] || continue
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    if [[ "$cmd" == *"bench build"* && ( "$cmd" == *"$ROOT"* || "$cwd" == "$ROOT" ) ]]; then
      printf '%s\n' "$pid"
    fi
  done < <(pgrep -af '[b]ench build' || true)
}

echo "=== NDS ERP SAUDI — QUIESCE RUNTIME SYNC SAFELY ==="
echo "ROOT=$ROOT"

if [ -s "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    old_cmd="$(tr '\0' ' ' < "/proc/$old_pid/cmdline" 2>/dev/null || true)"
    old_cwd="$(readlink -f "/proc/$old_pid/cwd" 2>/dev/null || true)"
    if [[ "$old_cmd" == *"$ROOT/codespace-runtime-sync.sh"* && "$old_cwd" == "$ROOT" ]]; then
      echo "RUNTIME_SYNC_STOP_REQUESTED=PID:$old_pid"
      kill -TERM "$old_pid" 2>/dev/null || true
    else
      echo "RUNTIME_SYNC_PID_FILE=STALE_OR_UNRELATED"
    fi
  else
    echo "RUNTIME_SYNC_WORKER=NOT_RUNNING"
  fi
else
  echo "RUNTIME_SYNC_PID_FILE=NOT_PRESENT"
fi

# A terminated shell may leave its current child build alive. Wait for all
# project-local sync children to finish; never kill build processes or delete locks.
for attempt in $(seq 1 180); do
  mapfile -t pids < <(runtime_sync_pids)
  if [ "${#pids[@]}" -eq 0 ]; then
    echo "RUNTIME_SYNC_QUIESCED=PASS"
    break
  fi
  if [ "$attempt" -eq 180 ]; then
    echo "RUNTIME_SYNC_QUIESCED=FAIL:STILL_RUNNING:${pids[*]}"
    exit 31
  fi
  if (( attempt % 12 == 0 )); then
    echo "RUNTIME_SYNC_WAITING_FOR_CHILDREN=${pids[*]}"
  fi
  sleep 5
done

for attempt in $(seq 1 180); do
  mapfile -t pids < <(bench_build_pids)
  if [ "${#pids[@]}" -eq 0 ]; then
    echo "BENCH_BUILD_QUIESCED=PASS"
    echo "BENCH_BUILD_LOCK_DELETED=NO"
    exit 0
  fi
  if [ "$attempt" -eq 180 ]; then
    echo "BENCH_BUILD_QUIESCED=FAIL:STILL_RUNNING:${pids[*]}"
    exit 32
  fi
  if (( attempt % 12 == 0 )); then
    echo "BENCH_BUILD_WAITING_FOR_COMPLETION=${pids[*]}"
  fi
  sleep 5
done
