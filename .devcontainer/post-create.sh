#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
cd "$ROOT"

echo "=== NDS ERP SAUDI CODESPACE BOOTSTRAP ==="
export PATH="$HOME/.local/bin:$PATH"

DB_ROOT_PASSWORD="nds_codespace_root"
SITE="ndserpsa.nds-sa.com"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential libffi-dev libjpeg-dev libmariadb-dev libmariadb-dev-compat \
  libssl-dev mariadb-client mariadb-server redis-server pkg-config xvfb fontconfig libfontconfig1 curl iproute2

sudo corepack enable
sudo corepack prepare yarn@1.22.22 --activate

sudo service mariadb start
sudo mariadb -e "ALTER USER root@localhost IDENTIFIED BY 'nds_codespace_root'; FLUSH PRIVILEGES;"

if ! command -v bench >/dev/null 2>&1; then
  python3 -m pip install --user --break-system-packages "frappe-bench==5.31.0"
fi

mkdir -p sites logs config
cp bench/apps.txt sites/apps.txt

python3 - <<'PY'
from pathlib import Path
import json

root = Path("/workspaces/ndserp-sa")
src = root / "bench/common_site_config.json"
dst = root / "sites/common_site_config.json"
cfg = json.loads(src.read_text())
cfg.update({
    "default_site": "ndserpsa.nds-sa.com",
    "serve_default_site": True,
    "dns_multitenant": True,
    "webserver_port": 6000,
    "socketio_port": 9000,
    "file_watcher_port": 6787,
    "redis_cache": "redis://127.0.0.1:13000",
    "redis_queue": "redis://127.0.0.1:11000",
    "redis_socketio": "redis://127.0.0.1:13000"
})
dst.write_text(json.dumps(cfg, indent=2) + "\n")
PY

cp bench/Procfile Procfile
sed -i 's/--port 8000/--port 6000/g' Procfile

if [ ! -d env ]; then
  python3 -m venv env
fi
./env/bin/python -m pip install --upgrade pip setuptools wheel

echo "=== PREPARE PYTHON ENV ==="
mkdir -p "$ROOT/env/lib/python3.14/site-packages"
printf '%s\n' "/workspaces/ndserp-sa/apps" > "$ROOT/env/lib/python3.14/site-packages/nds_apps.pth"

if grep -qx "changai" bench/apps.txt 2>/dev/null; then
  echo "=== INSTALL CPU-ONLY PYTORCH FOR CHANGAI ==="
  ./env/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
fi

echo "=== INSTALL PYTHON APPS ==="
while IFS= read -r app; do
  [ -z "$app" ] && continue
  app_dir="$ROOT/apps/$app"
  if [ -f "$app_dir/pyproject.toml" ] || [ -f "$app_dir/setup.py" ] || [ -f "$app_dir/setup.cfg" ]; then
    echo "--- Python: $app"
    if [ "$app" = "erpnext" ]; then
      echo "ERPNext is source-loaded via PYTHONPATH; no standalone pip package metadata required."
    elif [ "$app" = "pos_next" ]; then
      ./env/bin/pip install -e "$app_dir" --no-deps
    else
      ./env/bin/pip install -e "$app_dir"
    fi
  fi
done < bench/apps.txt

echo "=== INSTALL NODE DEPENDENCIES ==="
while IFS= read -r app; do
  [ -z "$app" ] && continue
  app_dir="$ROOT/apps/$app"
  if [ -f "$app_dir/package.json" ]; then
    echo "--- Node: $app"
    (
      cd "$app_dir"
      if [ -f yarn.lock ]; then
        yarn install --frozen-lockfile --non-interactive
      else
        yarn install --non-interactive
      fi
    )
  fi
done < bench/apps.txt

echo "=== VERIFY PYTHON IMPORTS ==="
./env/bin/python -c 'import frappe; print("FRAPPE_IMPORT=PASS"); print("FRAPPE_VERSION=", getattr(frappe, "__version__", "unknown"))'

echo "=== BENCH RUNTIME CONFIG ==="
bench setup redis
bench setup socketio

echo "=== BUILD ASSETS ==="
bench build

mkdir -p "sites/$SITE"

SITE_FROM_SECRET=0
DB_RESTORED=0

if [ -n "${NDSERP_SITE_CONFIG_JSON:-}" ]; then
  printf '%s' "$NDSERP_SITE_CONFIG_JSON" > "sites/$SITE/site_config.json"
  chmod 600 "sites/$SITE/site_config.json"

  python3 - <<'PY'
from pathlib import Path
import json

p = Path("/workspaces/ndserp-sa/sites/ndserpsa.nds-sa.com/site_config.json")
cfg = json.loads(p.read_text())
cfg["db_host"] = "mariadb"
cfg["db_port"] = 3306
p.write_text(json.dumps(cfg, indent=2) + "\n")
if not cfg.get("db_name"):
    raise SystemExit("NDSERP_SITE_CONFIG_JSON must contain db_name for database restore.")
PY

  SITE_FROM_SECRET=1
  echo "SITE_CONFIG=FROM_CODESPACES_SECRET"
fi

if [ -n "${NDSERP_DB_DUMP_URL:-}" ]; then
  if [ "$SITE_FROM_SECRET" -ne 1 ]; then
    echo "ERROR: NDSERP_DB_DUMP_URL requires NDSERP_SITE_CONFIG_JSON." >&2
    exit 1
  fi

  DB_NAME=$(./env/bin/python - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path("/workspaces/ndserp-sa/sites/ndserpsa.nds-sa.com/site_config.json").read_text())
print(cfg["db_name"])
PY
)
  DB_USER=$(./env/bin/python - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path("/workspaces/ndserp-sa/sites/ndserpsa.nds-sa.com/site_config.json").read_text())
print(cfg.get("db_user") or cfg["db_name"])
PY
)
  DB_PASSWORD=$(./env/bin/python - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path("/workspaces/ndserp-sa/sites/ndserpsa.nds-sa.com/site_config.json").read_text())
print(cfg.get("db_password", ""))
PY
)

  ./env/bin/python - "$DB_NAME" "$DB_USER" "$DB_PASSWORD" <<'PY' > /tmp/nds_restore.sql
import sys

db_name, db_user, db_password = sys.argv[1:4]

def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"

if not db_name.replace("_", "").isalnum():
    raise SystemExit("Unsafe db_name in NDSERP_SITE_CONFIG_JSON")

print(f"DROP DATABASE IF EXISTS {db_name};")
print(f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
print(f"CREATE USER IF NOT EXISTS {sql_string(db_user)}@'%' IDENTIFIED BY {sql_string(db_password)};")
print(f"ALTER USER {sql_string(db_user)}@'%' IDENTIFIED BY {sql_string(db_password)};")
print(f"GRANT ALL PRIVILEGES ON {db_name}.* TO {sql_string(db_user)}@'%';")
print("FLUSH PRIVILEGES;")
PY

  mariadb -h "$NDSERP_DB_HOST" -P "$NDSERP_DB_PORT" -uroot -p"$DB_ROOT_PASSWORD" < /tmp/nds_restore.sql
  rm -f /tmp/nds_restore.sql

  mkdir -p /tmp/nds-restore
  curl -fL --retry 3 --retry-all-errors "$NDSERP_DB_DUMP_URL" -o /tmp/nds-restore/database.sql.gz
  gzip -dc /tmp/nds-restore/database.sql.gz | mariadb -h "$NDSERP_DB_HOST" -P "$NDSERP_DB_PORT" -uroot -p"$DB_ROOT_PASSWORD" "$DB_NAME"
  echo "DB_RESTORE=PASS"
  DB_RESTORED=1
fi

if [ "$SITE_FROM_SECRET" -ne 1 ]; then
  echo "=== CREATE CLEAN SAUDI DEVELOPMENT SITE ==="
  bench new-site "$SITE" \
    --db-type mariadb \
    --db-host "$NDSERP_DB_HOST" \
    --db-port "$NDSERP_DB_PORT" \
    --db-root-username root \
    --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password admin \
    --set-default
fi

echo "=== INSTALL SAUDI APPS ==="
if [ "$DB_RESTORED" -eq 1 ]; then
  echo "Production database restored: no install-app/migrate step is performed."
  bench --site "$SITE" list-apps
else
  installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null | awk '{print $1}' || true)"
  if ! printf '%s\n' "$installed_apps" | grep -qx "ERPNext"; then
    echo "--- Install dependency root: erpnext"
    bench --site "$SITE" install-app erpnext --skip-assets
  fi

  while IFS= read -r app; do
    [ -z "$app" ] && continue
    [ "$app" = "frappe" ] && continue
    [ "$app" = "erpnext" ] && continue
    installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null | awk '{print $1}' || true)"
    if ! printf '%s\n' "$installed_apps" | grep -qx "$app"; then
      echo "--- Install: $app"
      bench --site "$SITE" install-app "$app" --skip-assets
    fi
  done < bench/apps.txt
fi

if [ -n "${NDSERP_FILES_ARCHIVE_URL:-}" ]; then
  mkdir -p /tmp/nds-restore/files
  curl -fL --retry 3 --retry-all-errors "$NDSERP_FILES_ARCHIVE_URL" -o /tmp/nds-restore/files/files.tar.gz
  rm -rf /tmp/nds-restore/files/extracted
  mkdir -p /tmp/nds-restore/files/extracted
  tar -xzf /tmp/nds-restore/files/files.tar.gz -C /tmp/nds-restore/files/extracted

  for area in "public/files" "private/files"; do
    src=""
    while IFS= read -r candidate; do
      src="$candidate"
      break
    done < <(find /tmp/nds-restore/files/extracted -type d -path "*/$area" -print)

    if [ -n "$src" ]; then
      mkdir -p "sites/$SITE/$area"
      cp -a "$src"/. "sites/$SITE/$area"/
      echo "FILES_RESTORE_$area=PASS"
    fi
  done
fi

bench --site "$SITE" set-config developer_mode 1
bench --site "$SITE" clear-cache

echo
echo "=== CODESPACE READY ==="
echo "Repository: https://github.com/moh222salah/ndserp-sa"
echo "Site: $SITE"
echo "Application port: 6000"
echo "Local runtime check: http://127.0.0.1:6000/"
echo "Start with: bench start"
