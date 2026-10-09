#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
SITE_DIR="$ROOT/sites/$SITE"
POLICY_MARKER="$ROOT/sites/.nds-custom-report-cleanup-v1"
BACKUP_ROOT="$HOME/nds-sa-local-backups"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/custom-reports-$STAMP"
MUTATION_STARTED=0
COMPLETED=0

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
mkdir -p "$ROOT/logs" "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"

on_error() {
  rc=$?
  trap - ERR
  echo "CUSTOM_REPORT_CLEANUP=FAIL"
  echo "EXIT_CODE=$rc"
  if [ -d "$BACKUP_DIR" ]; then
    echo "BACKUP_DIR=$BACKUP_DIR"
  fi
  if [ "$MUTATION_STARTED" -eq 1 ] && [ "$COMPLETED" -ne 1 ]; then
    echo "ROLLBACK_REQUIRED=YES"
    echo "BACKUP_PRESERVED=YES"
    echo "Do not delete the backup directory; restore the database/files before retrying."
  fi
  exit "$rc"
}
trap on_error ERR

echo "=== NDS ERP SAUDI — BACKUP-FIRST CUSTOM REPORT CLEANUP ==="
echo "ROOT=$ROOT"
echo "SITE=$SITE"

[ "$(pwd -P)" = "$ROOT" ] || { echo "ROOT_CHECK=FAIL"; exit 10; }
[ -s "$SITE_DIR/site_config.json" ] || { echo "LOCAL_SITE_CONFIG=FAIL"; exit 11; }
[ -x "$ROOT/env/bin/python" ] || { echo "PYTHON_ENV=FAIL"; exit 12; }

# This automation is strictly for the isolated local Codespace DB. Never write
# to a remote or production database.
"$ROOT/env/bin/python" - "$SITE_DIR/site_config.json" "$ROOT/sites/common_site_config.json" <<'PY'
import json
import sys
from pathlib import Path

site_path = Path(sys.argv[1])
common_path = Path(sys.argv[2])
site_cfg = json.loads(site_path.read_text(encoding="utf-8"))
common_cfg = json.loads(common_path.read_text(encoding="utf-8")) if common_path.is_file() else {}
cfg = {**common_cfg, **site_cfg}
host = str(cfg.get("db_host") or "localhost").strip().lower()
allowed = {"", "localhost", "127.0.0.1", "::1"}
if host not in allowed:
    raise SystemExit(f"LOCAL_DB_GUARD=FAIL:NON_LOCAL_DB_HOST:{host}")
print("LOCAL_DB_GUARD=PASS")
print(f"LOCAL_DB_HOST={host or 'localhost (default)'}")
PY

if [ -s "$POLICY_MARKER" ]; then
  echo "CUSTOM_REPORT_POLICY=ALREADY_APPLIED"
  echo "DB_WRITE=NO"
  echo "PRODUCTION_DB_WRITE=NO"
  echo "CORE_MODIFICATION=NO"
  echo "MIGRATION=NO"
  exit 0
fi

bench --site "$SITE" list-apps | tee "$ROOT/logs/custom-reports-installed-apps.log"
grep -Eq '^ndserp([[:space:]]|$)' "$ROOT/logs/custom-reports-installed-apps.log" || {
  echo "NDSERP_SITE_APP=FAIL"
  exit 13
}

count_reports() {
  local output
  output="$(bench --site "$SITE" execute ndserp.setup.custom_report_policy.count_nonstandard_reports 2>&1)" || {
    printf '%s\n' "$output"
    echo "REPORT_COUNT_QUERY=FAIL"
    return 20
  }
  printf '%s\n' "$output" >> "$ROOT/logs/custom-reports-policy.log"
  local count
  count="$(printf '%s\n' "$output" | grep -E '^[0-9]+$' | tail -n 1 || true)"
  [ -n "$count" ] || {
    echo "REPORT_COUNT_PARSE=FAIL"
    printf '%s\n' "$output"
    return 21
  }
  printf '%s\n' "$count"
}

COUNT_BEFORE="$(count_reports)"
echo "NONSTANDARD_REPORTS_BEFORE=$COUNT_BEFORE"

if [ "$COUNT_BEFORE" -eq 0 ]; then
  printf '%s\n' "$(git rev-parse HEAD)" > "$POLICY_MARKER"
  echo "NDS_CUSTOM_REPORT_PURGE=PASS deleted=0 remaining=0"
  echo "CUSTOM_REPORT_POLICY=MARKED"
  echo "BACKUP_REQUIRED=NO_NO_RECORDS_TO_DELETE"
  echo "DB_WRITE=NO"
  echo "PRODUCTION_DB_WRITE=NO"
  echo "CORE_MODIFICATION=NO"
  echo "MIGRATION=NO"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
cp -p "$SITE_DIR/site_config.json" "$BACKUP_DIR/site_config.json"
chmod 600 "$BACKUP_DIR/site_config.json"
if [ -s "$ROOT/sites/common_site_config.json" ]; then
  cp -p "$ROOT/sites/common_site_config.json" "$BACKUP_DIR/common_site_config.json"
  chmod 600 "$BACKUP_DIR/common_site_config.json"
fi
printf '%s\n' "$(git rev-parse HEAD)" > "$BACKUP_DIR/source-head.txt"
printf '%s\n' "$SITE" > "$BACKUP_DIR/site-name.txt"
printf '%s\n' "$COUNT_BEFORE" > "$BACKUP_DIR/nonstandard-reports-count.before.txt"

echo "=== CREATE DATABASE + FILES BACKUP BEFORE DELETION ==="
bench --site "$SITE" backup --with-files --compress --backup-path "$BACKUP_DIR" \
  2>&1 | tee "$BACKUP_DIR/backup.log"

DB_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*-database*.sql.gz' -o -name '*-database*.sql' \) -size +0c -print -quit)"
[ -n "$DB_BACKUP" ] || { echo "DATABASE_BACKUP=FAIL"; exit 22; }
case "$DB_BACKUP" in
  *.gz) gzip -t "$DB_BACKUP" ;;
esac
echo "DATABASE_BACKUP=PASS"
echo "DATABASE_BACKUP_FILE=$(basename "$DB_BACKUP")"

(
  cd "$BACKUP_DIR"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 -r sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)
chmod 600 "$BACKUP_DIR/SHA256SUMS"
echo "BACKUP_STATUS=CONFIRMED"
echo "BACKUP_DIR=$BACKUP_DIR"

echo "=== DELETE NON-STANDARD REPORT RECORDS ==="
MUTATION_STARTED=1
PURGE_OUTPUT="$(bench --site "$SITE" execute ndserp.setup.custom_report_policy.purge_nonstandard_reports 2>&1)" || {
  printf '%s\n' "$PURGE_OUTPUT"
  echo "REPORT_PURGE=FAIL"
  echo "ROLLBACK_REQUIRED=YES"
  echo "BACKUP_PRESERVED=YES"
  echo "BACKUP_DIR=$BACKUP_DIR"
  exit 23
}
printf '%s\n' "$PURGE_OUTPUT" | tee "$BACKUP_DIR/purge-output.log"

COUNT_AFTER="$(count_reports)"
echo "NONSTANDARD_REPORTS_AFTER=$COUNT_AFTER"
[ "$COUNT_AFTER" -eq 0 ] || { echo "REPORT_PURGE=FAIL:NONZERO_REMAINING"; exit 24; }

printf '%s\n' "$COUNT_AFTER" > "$BACKUP_DIR/nonstandard-reports-count.after.txt"
(
  cd "$BACKUP_DIR"
  sha256sum nonstandard-reports-count.before.txt nonstandard-reports-count.after.txt > cleanup-counts.SHA256SUMS
  sha256sum -c cleanup-counts.SHA256SUMS
)

printf '%s\n' "$(git rev-parse HEAD)" > "$POLICY_MARKER"
COMPLETED=1
echo "NDS_CUSTOM_REPORT_PURGE=PASS"
echo "CUSTOM_REPORT_POLICY=MARKED"
echo "REPORTS_DELETED=$COUNT_BEFORE"
echo "REPORTS_REMAINING=0"
echo "BACKUP_STATUS=CONFIRMED"
echo "BACKUP_DIR=$BACKUP_DIR"
echo "DB_WRITE=YES_LOCAL_SITE_ONLY"
echo "PRODUCTION_DB_WRITE=NO"
echo "EGYPT_ERP_MODIFICATION=NO"
echo "CORE_MODIFICATION=NO"
echo "MIGRATION=NO"
echo "SSH/WSL session remains open — no logout / no exit."
