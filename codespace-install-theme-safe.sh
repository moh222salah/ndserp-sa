#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
SITE_DIR="$ROOT/sites/$SITE"
BACKUP_ROOT="$HOME/nds-sa-local-backups"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
MUTATION_STARTED=0
COMPLETED=0
BEFORE_LIST=""

cd "$ROOT"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_ROOT" "$BACKUP_DIR"

on_error() {
  rc=$?
  trap - ERR
  echo "INSTALL_FLOW=FAIL"
  echo "EXIT_CODE=$rc"
  echo "BACKUP_DIR=$BACKUP_DIR"
  if [ "$MUTATION_STARTED" -eq 1 ] && [ "$COMPLETED" -ne 1 ]; then
    echo "ROLLBACK_REQUIRED=YES"
    echo "BACKUP_PRESERVED=YES"
    echo "Do not delete the backup directory; restore the database/files before retrying."
  fi
  exit "$rc"
}
trap on_error ERR

echo "=== NDS ERP SAUDI — LOCAL THEME INSTALL WITH BACKUP ==="
echo "ROOT=$ROOT"
echo "SITE=$SITE"
echo "BACKUP_DIR=$BACKUP_DIR"

[ "$(pwd -P)" = "$ROOT" ] || { echo "ROOT_CHECK=FAIL"; exit 10; }
[ -s "$SITE_DIR/site_config.json" ] || { echo "LOCAL_SITE_CONFIG=FAIL"; exit 11; }
[ -s "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py" ] || { echo "THEME_SOURCE=FAIL"; exit 12; }
[ -x "$ROOT/env/bin/python" ] || { echo "PYTHON_ENV=FAIL"; exit 13; }

# Guard against accidentally using a remote/production database.
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

echo "=== VERIFY SITE / DATABASE ACCESS ==="
bench --site "$SITE" list-apps | tee "$BACKUP_DIR/installed-apps.before.txt"

# Save site configuration separately (credentials are kept private to this user).
cp -p "$SITE_DIR/site_config.json" "$BACKUP_DIR/site_config.json"
chmod 600 "$BACKUP_DIR/site_config.json"
if [ -s "$ROOT/sites/common_site_config.json" ]; then
  cp -p "$ROOT/sites/common_site_config.json" "$BACKUP_DIR/common_site_config.json"
  chmod 600 "$BACKUP_DIR/common_site_config.json"
fi
if [ -s "$ROOT/sites/assets/assets.json" ]; then
  cp -p "$ROOT/sites/assets/assets.json" "$BACKUP_DIR/assets.json.before.json"
fi
printf '%s\n' "$(git rev-parse HEAD)" > "$BACKUP_DIR/source-head.txt"
printf '%s\n' "$SITE" > "$BACKUP_DIR/site-name.txt"

echo "=== CREATE DATABASE + FILES BACKUP BEFORE INSTALL ==="
BEFORE_LIST="$(mktemp)"
trap 'rm -f "$BEFORE_LIST"' EXIT
mkdir -p "$SITE_DIR/private/backups"
find "$SITE_DIR/private/backups" -maxdepth 1 -type f -printf '%f\n' | sort > "$BEFORE_LIST"

# --backup-path places the snapshot outside the site tree; --with-files includes public/private files.
bench --site "$SITE" backup --with-files --compress --backup-path "$BACKUP_DIR" \
  2>&1 | tee "$BACKUP_DIR/backup.log"

DB_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*-database*.sql.gz' -o -name '*-database*.sql' \) -size +0c -print -quit)"
if [ -z "$DB_BACKUP" ]; then
  # Compatibility fallback if this Bench version writes the backup into the site's default folder.
  while IFS= read -r file; do
    [ -n "$file" ] || continue
    if ! grep -Fxq "$file" "$BEFORE_LIST"; then
      cp -p "$SITE_DIR/private/backups/$file" "$BACKUP_DIR/"
    fi
  done < <(find "$SITE_DIR/private/backups" -maxdepth 1 -type f -printf '%f\n')
  DB_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*-database*.sql.gz' -o -name '*-database*.sql' \) -size +0c -print -quit)"
fi
[ -n "$DB_BACKUP" ] || { echo "DATABASE_BACKUP=FAIL"; exit 20; }
echo "DATABASE_BACKUP=PASS"
echo "DATABASE_BACKUP_FILE=$(basename "$DB_BACKUP")"

# Confirm site_config backup and produce immutable checksums before any site mutation.
test -s "$BACKUP_DIR/site_config.json"
(
  cd "$BACKUP_DIR"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 -r sha256sum > SHA256SUMS
)
chmod 600 "$BACKUP_DIR/SHA256SUMS"
echo "BACKUP_FILES:"
find "$BACKUP_DIR" -maxdepth 1 -type f -printf '%f %s bytes\n' | sort
echo "BACKUP_STATUS=CONFIRMED"

echo "=== CHECK APP INSTALLATION STATUS ==="
APPS_BEFORE="$(cat "$BACKUP_DIR/installed-apps.before.txt")"
if printf '%s\n' "$APPS_BEFORE" | grep -q '^Amir Theme'; then
  echo "AMIR_THEME_SITE_APP=ALREADY_INSTALLED"
else
  echo "=== INSTALL AMIR THEME ON THIS LOCAL SITE ONLY ==="
  MUTATION_STARTED=1
  bench --site "$SITE" install-app amir_theme_v16 \
    2>&1 | tee "$BACKUP_DIR/install-app.log"
  bench --site "$SITE" list-apps | tee "$BACKUP_DIR/installed-apps.after.txt"
  grep -q '^Amir Theme' "$BACKUP_DIR/installed-apps.after.txt"
  echo "AMIR_THEME_SITE_APP=PASS"
fi

echo "=== BUILD PRODUCTION THEME ASSETS ==="
bench build --app amir_theme_v16 --production 2>&1 | tee "$BACKUP_DIR/asset-build.log"
bash apps/amir_theme_v16/scripts/harden_assets.sh \
  2>&1 | tee "$BACKUP_DIR/asset-hardening.log"
bench --site "$SITE" clear-cache
printf '%s\n' "$(git rev-parse HEAD)" > sites/.nds-runtime-source-head

echo "=== START / VERIFY LOCAL BENCH SERVER ==="
bash codespace-start-server.sh 2>&1 | tee "$BACKUP_DIR/server-check.log"

echo "=== VERIFY BUILT CSS AGAINST SERVED CSS ==="
bash codespace-verify-runtime.sh 2>&1 | tee "$BACKUP_DIR/runtime-verification.log"
grep -q '^HEADER_RUNTIME_VERIFICATION=PASS$' "$BACKUP_DIR/runtime-verification.log"
grep -q '^SERVED_HEADER_CSS_MATCH=PASS$' "$BACKUP_DIR/runtime-verification.log"

COMPLETED=1
echo "=== LOCAL THEME INSTALL COMPLETE ==="
echo "AMIR_THEME_SITE_APP=PASS"
echo "ASSET_BUILD=PASS"
echo "BACKUP_STATUS=CONFIRMED"
echo "HEADER_RUNTIME_VERIFICATION=PASS"
echo "BACKUP_DIR=$BACKUP_DIR"
echo "DB_WRITE=YES_LOCAL_SITE_ONLY"
echo "PRODUCTION_DB_WRITE=NO"
echo "EGYPT_ERP_MODIFICATION=NO"
echo "CORE_MODIFICATION=NO"
echo "SSH/WSL session remains open — no logout / no exit."
