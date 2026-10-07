#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
cd "$ROOT"

echo "=== NDS ERP SAUDI CODESPACE BOOTSTRAP ==="

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y   build-essential libffi-dev libjpeg-dev libmariadb-dev libmariadb-dev-compat   libssl-dev mariadb-client redis-server pkg-config xvfb fontconfig libfontconfig1

corepack enable
corepack prepare yarn@1.22.22 --activate

if ! command -v bench >/dev/null 2>&1; then
  python3 -m pip install --user "frappe-bench==5.31.0"
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
sed -i 's/--port 8000/--port 6000/' Procfile

if [ ! -d env ]; then
  python3 -m venv env
fi
./env/bin/python -m pip install --upgrade pip setuptools wheel

echo "=== INSTALL PYTHON APPS ==="
while IFS= read -r app; do
  [ -z "$app" ] && continue
  app_dir="$ROOT/apps/$app"
  if [ -f "$app_dir/pyproject.toml" ] || [ -f "$app_dir/setup.py" ] || [ -f "$app_dir/setup.cfg" ]; then
    echo "--- Python: $app"
    ./env/bin/pip install -e "$app_dir"
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

echo "=== BENCH RUNTIME CONFIG ==="
bench setup redis
bench setup socketio

echo "=== BUILD ASSETS ==="
bench build

SITE="ndserpsa.nds-sa.com"
mkdir -p "sites/$SITE"

if [ -n "${NDSERP_SITE_CONFIG_JSON:-}" ]; then
  printf '%s' "$NDSERP_SITE_CONFIG_JSON" > "sites/$SITE/site_config.json"
  echo "SITE_CONFIG=FROM_CODESPACES_SECRET"
fi

if [ ! -f "sites/$SITE/site_config.json" ]; then
  echo "=== CREATE CLEAN SAUDI DEVELOPMENT SITE ==="
  bench new-site "$SITE"     --db-type mariadb     --db-host "$NDSERP_DB_HOST"     --db-port "$NDSERP_DB_PORT"     --db-root-username root     --db-root-password nds_codespace_root     --admin-password admin     --set-default
fi

echo "=== INSTALL SAUDI APPS ==="
while IFS= read -r app; do
  [ -z "$app" ] && continue
  [ "$app" = "frappe" ] && continue
  if ! bench --site "$SITE" list-apps 2>/dev/null | awk '{print $1}' | grep -qx "$app"; then
    echo "--- Install: $app"
    bench --site "$SITE" install-app "$app" --skip-assets
  fi
done < bench/apps.txt

if [ -n "${NDSERP_FILES_ARCHIVE_URL:-}" ]; then
  mkdir -p /tmp/nds-restore
  curl -fL "$NDSERP_FILES_ARCHIVE_URL" -o /tmp/nds-restore/files.tar.gz
  tar -xzf /tmp/nds-restore/files.tar.gz -C "sites/$SITE"
  echo "FILES_RESTORE=PASS"
fi

bench --site "$SITE" set-config developer_mode 1
bench --site "$SITE" clear-cache

echo
echo "=== CODESPACE READY ==="
echo "Repository: https://github.com/moh222salah/ndserp-sa"
echo "Site: $SITE"
echo "Application port: 6000"
echo "Start with: bench start"
