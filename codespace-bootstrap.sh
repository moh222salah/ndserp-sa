#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
SITE="ndserpsa.nds-sa.com"
BENCH_VERSION="5.31.0"
ERPNEXT_VERSION="v16.36.1"
DB_ROOT_PASSWORD="nds_codespace_root"

cd "$ROOT"

# Always consume the GitHub source-of-truth before installing/building runtime assets.
git fetch origin main
git pull --ff-only origin main

echo "SOURCE_OF_TRUTH=$(git rev-parse --short HEAD)"

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"


verify_amir_source() {
  test -s "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'app_include_css = "amir_theme.bundle.css"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'app_include_js = "amir_theme.bundle.js"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'web_include_css = "login_brand.bundle.css"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  grep -Fq 'web_include_js = "login_brand.bundle.js"' "$ROOT/apps/amir_theme_v16/amir_theme_v16/hooks.py"
  "$ROOT/env/bin/python" -c 'import amir_theme_v16; print("AMIR_THEME_PYTHON_IMPORT=PASS")'
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
        required_header_markers = ("body .navbar", "58px", "#0a2342")
        missing = [marker for marker in required_header_markers if marker not in css]
        if missing:
            raise SystemExit("MODERN_HEADER_CSS=FAIL:MISSING_MARKERS:" + ",".join(missing))
        print("MODERN_HEADER_CSS=PASS")

print("ASSET_SERVE_TREE=PASS")
PY
}

echo "=== NDS ERP SAUDI CODESPACE ==="
echo "ROOT=$ROOT"
echo "SITE=$SITE"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential pkg-config curl git \
  libffi-dev libssl-dev libjpeg-dev libmariadb-dev libmariadb-dev-compat \
  mariadb-server mariadb-client redis-server \
  xvfb fontconfig libfontconfig1

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv python install 3.14
PYTHON_BIN="$(uv python find 3.14)"
echo "PYTHON=$PYTHON_BIN"
"$PYTHON_BIN" --version

sudo service mariadb start

if sudo mariadb -uroot -p"$DB_ROOT_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; then
  echo "MARIADB_ROOT_AUTH=PASSWORD"
elif sudo mariadb -e "SELECT 1" >/dev/null 2>&1; then
  sudo mariadb -e "ALTER USER root@localhost IDENTIFIED BY '$DB_ROOT_PASSWORD'; FLUSH PRIVILEGES;"
  echo "MARIADB_ROOT_AUTH=SOCKET_SET"
else
  echo "MARIADB_ROOT_AUTH=FAIL"
  exit 1
fi

sudo service redis-server start || true

if ! command -v bench >/dev/null 2>&1; then
  "$PYTHON_BIN" -m pip install --user --break-system-packages "frappe-bench==${BENCH_VERSION}"
fi
export PATH="$HOME/.local/bin:$PATH"
bench --version

mkdir -p sites logs config
cp bench/apps.txt sites/apps.txt

echo "=== VERIFY/REPAIR ERPNEXT SOURCE ==="
if [ ! -s "$ROOT/apps/erpnext/erpnext/__init__.py" ] || [ ! -s "$ROOT/apps/erpnext/erpnext/hooks.py" ] || [ ! -s "$ROOT/apps/erpnext/erpnext/modules.txt" ]; then
  echo "ERPNext source is incomplete; replacing it with official ERPNext ${ERPNEXT_VERSION}."
  rm -rf "$ROOT/apps/erpnext"
  git clone --depth 1 --branch "$ERPNEXT_VERSION" https://github.com/frappe/erpnext.git "$ROOT/apps/erpnext"
fi
test -s "$ROOT/apps/erpnext/erpnext/__init__.py"
test -s "$ROOT/apps/erpnext/erpnext/hooks.py"
test -s "$ROOT/apps/erpnext/erpnext/modules.txt"
echo "ERPNEXT_SOURCE=PASS"

if [ ! -x env/bin/python ]; then
  "$PYTHON_BIN" -m venv env
fi
./env/bin/python -m pip install --upgrade pip setuptools wheel

SITE_PACKAGES="$(./env/bin/python -c 'import site; print(site.getsitepackages()[0])')"
printf '%s\n' "$ROOT/apps" > "$SITE_PACKAGES/nds_apps.pth"

echo "=== INSTALL FRAPPE CORE ==="
./env/bin/pip install -e "$ROOT/apps/frappe"

echo "=== INSTALL SAUDI APP PYTHON PACKAGES ==="
while IFS= read -r app; do
  [ -z "$app" ] && continue
  [ "$app" = "frappe" ] && continue
  app_dir="$ROOT/apps/$app"

  if [ ! -d "$app_dir" ]; then
    echo "MISSING_APP=$app"
    continue
  fi

  if [ "$app" = "erpnext" ]; then
    echo "ERPNext: source-loaded; no standalone package install."
  elif [ "$app" = "pos_next" ]; then
    ./env/bin/pip install -e "$app_dir" --no-deps
  elif [ "$app" = "changai" ]; then
    echo "ChangAI source-loaded first; CPU ML dependency installed below."
    ./env/bin/pip install -e "$app_dir"

  elif [ -f "$app_dir/pyproject.toml" ] || [ -f "$app_dir/setup.py" ] || [ -f "$app_dir/setup.cfg" ]; then
    ./env/bin/pip install -e "$app_dir"
  fi
done < bench/apps.txt

if grep -qx "changai" bench/apps.txt 2>/dev/null; then
  echo "=== INSTALL CPU PYTORCH ONLY ==="
  ./env/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
fi

echo "=== INSTALL YARN ==="
sudo corepack enable
sudo corepack prepare yarn@1.22.22 --activate
yarn --version

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
    "webserver_port": 8080,
    "socketio_port": 9000,
    "file_watcher_port": 6787,
    "redis_cache": "redis://127.0.0.1:13000",
    "redis_queue": "redis://127.0.0.1:11000",
    "redis_socketio": "redis://127.0.0.1:13000"
})
dst.write_text(json.dumps(cfg, indent=2) + "\n")
PY

cp bench/Procfile Procfile
if ! grep -q '^runtime-sync:' Procfile; then
  printf '%s\n' 'runtime-sync: bash codespace-runtime-sync.sh' >> Procfile
fi

bench setup redis
bench setup socketio

./env/bin/python -c 'import frappe; print("FRAPPE_IMPORT=PASS"); print("FRAPPE_VERSION=", getattr(frappe, "__version__", "unknown"))'

CREATED_CLEAN_SITE=0
if [ ! -f "sites/$SITE/site_config.json" ]; then
  echo "=== CREATE CLEAN SAUDI SITE ==="
  bench new-site "$SITE" \
    --db-type mariadb \
    --db-host 127.0.0.1 \
    --db-port 3306 \
    --db-root-username root \
    --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password admin \
    --set-default
  CREATED_CLEAN_SITE=1
fi

echo "=== INSTALL ERPNext ==="
installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null || true)"
if ! printf '%s\n' "$installed_apps" | grep -q '^ERPNext'; then
  if [ "$CREATED_CLEAN_SITE" -eq 1 ]; then
    bench --site "$SITE" install-app erpnext
  else
    echo "ERPNEXT_SITE_INSTALL=SKIPPED_EXISTING_SITE"
  fi
fi

echo "=== VERIFY/INSTALL AMIR THEME ON SITE ==="
verify_amir_source

installed_apps=""
if ! installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null)"; then
  echo "SITE_APP_QUERY=FAIL"
  echo "SAFE_BOUNDARY=STOP_BEFORE_SITE_WRITE"
  exit 21
fi

THEME_SITE_INSTALL=NO
if printf '%s\n' "$installed_apps" | grep -Eq '^(Amir Theme|amir_theme_v16)([[:space:]]|$)'; then
  echo "AMIR_THEME_SITE_APP=PASS"
else
  echo "AMIR_THEME_SITE_APP=MISSING_INSTALLING"
  echo "AMIR_THEME_SITE_DB_WRITE=THEME_APP_INSTALL_ONLY"
  bench --site "$SITE" install-app amir_theme_v16
  THEME_SITE_INSTALL=YES
  installed_apps="$(bench --site "$SITE" list-apps 2>/dev/null)"
  if ! printf '%s\n' "$installed_apps" | grep -Eq '^(Amir Theme|amir_theme_v16)([[:space:]]|$)'; then
    echo "AMIR_THEME_SITE_APP=FAIL_AFTER_INSTALL"
    exit 22
  fi
  echo "AMIR_THEME_SITE_APP=PASS_AFTER_INSTALL"
fi

echo "AMIR_THEME_SITE_INSTALL=$THEME_SITE_INSTALL"
echo "=== BUILD ASSETS ==="
bench build --app amir_theme_v16 --production
bash apps/amir_theme_v16/scripts/harden_assets.sh
verify_amir_assets

if bench --site "$SITE" list-apps 2>/dev/null | grep -Eq '^(Amir Theme|amir_theme_v16)([[:space:]]|$)'; then
  echo "AMIR_THEME_RUNTIME=PASS"
else
  echo "AMIR_THEME_RUNTIME=FAIL"
  exit 23
fi

bench --site "$SITE" clear-cache
echo "CORE_MODIFICATION=NO"
echo "MIGRATION=NO"

echo "=== START SAUDI ERP ==="
echo "Run: bench start"
echo "Port: 8080"
