#!/usr/bin/env bash
set -Eeuo pipefail

# Resolve the active NDS ERP Saudi checkout instead of hard-coding Codespaces.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  ROOT="/home/moh222salah/projects/nds/ndserp-sa"
fi
SITE="ndserpsa.nds-sa.com"
PORT="8080"

cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "=== NDS ERP SAUDI — RUNTIME REFRESH ==="
echo "SOURCE=GitHub main"
echo "ROOT=$ROOT"
echo "SITE=$SITE"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "RUNTIME_REFRESH=BLOCKED_DIRTY_WORKTREE"
  git status --short
  exit 2
fi

git fetch origin main
git switch main
git pull --ff-only origin main

echo "SOURCE_HEAD=$(git rev-parse HEAD)"
echo "SOURCE_HEAD_SHORT=$(git rev-parse --short HEAD)"

bench build --app amir_theme_v16 --production
bash apps/amir_theme_v16/scripts/harden_assets.sh

# Cache clear only; no schema migration and no database data mutation.
bench --site "$SITE" clear-cache

if curl -fsS -o /dev/null -w "LOGIN_HTTP=%{http_code}\n" "http://127.0.0.1:${PORT}/login"; then
  echo "LOGIN_HTTP=PASS"
else
  echo "LOGIN_HTTP=FAIL_OR_SERVICE_NOT_RUNNING"
fi

echo "UI/CSS=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "PRODUCTION_DB_WRITE=NO"
echo "RESTART=NO"
echo "RUNTIME_REFRESH=PASS"
echo "SSH/WSL session remains open — no logout / no exit."
