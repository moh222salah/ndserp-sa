#!/usr/bin/env bash
# One-time: push this folder to your GitHub repo.
# Run from the repo root (the folder containing this script).
set -e
REPO="${1:-https://github.com/mahmouddev19/contracting.git}"
git init
git branch -M main
git remote add origin "$REPO" 2>/dev/null || git remote set-url origin "$REPO"
git add .
git commit -m "Contracting app — full Project-rooted build"
echo "When prompted: username = your GitHub user, password = a Personal Access Token (repo scope)."
git push -u origin main
