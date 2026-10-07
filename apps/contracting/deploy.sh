#!/usr/bin/env bash
# Deploy the Contracting app on a Frappe/ERPNext bench from this git repo.
# Usage:  ./deploy.sh <site>     e.g.  ./deploy.sh erp16.nds-sa.com
set -e
SITE="${1:?Usage: ./deploy.sh <site>}"
BENCH="${BENCH_PATH:-$HOME/frappe-bench}"

echo "==> Pulling latest code"
git -C "$(dirname "$0")" pull --ff-only || true

echo "==> Ensuring app is installed in the bench env"
cd "$BENCH"
./env/bin/pip install -e apps/contracting >/dev/null

# install-app only the first time (ignore error if already installed)
bench --site "$SITE" install-app contracting 2>/dev/null || true

echo "==> Migrate (creates new doctypes, runs cleanup patch, provisions fields/roles/workspace)"
bench --site "$SITE" migrate

echo "==> Build assets + restart"
bench build
bench --site "$SITE" clear-cache
bench restart || true

echo "==> Done. Verify with Ctrl+K: 'Project Budget' exists, 'Construction Contract' is gone."
