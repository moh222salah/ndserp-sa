#!/usr/bin/env bash
#
# Post-build asset hardening for amir_theme_v16.
#
# Frappe's esbuild config hard-codes `sourcemap: true` (apps/frappe/esbuild/esbuild.js),
# so even `bench build --production` ships .map files containing `sourcesContent` —
# i.e. the complete original source, comments and all, publicly readable at
# /assets/amir_theme_v16/dist/**/*.map without so much as opening devtools.
#
# This script removes them after the build. It is safe by construction:
#   - sites/assets/assets.json never references a .map file, only the bundles.
#   - Browsers request a .map only when devtools is open, so nothing at runtime breaks.
#   - The [hash] in each filename is fixed at build time and recorded in assets.json;
#     editing file contents afterwards does not invalidate that reference.
#   - public/dist/ is gitignored, so nothing here touches the repository.
#
# Run it AFTER every build — the build regenerates dist/ and puts the maps back:
#
#   bench build --app amir_theme_v16 --production
#   bash apps/amir_theme_v16/scripts/harden_assets.sh
#
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$APP_DIR/amir_theme_v16/public/dist"

if [ ! -d "$DIST" ]; then
	echo "error: dist not found at $DIST — run 'bench build --app amir_theme_v16 --production' first" >&2
	exit 1
fi

# 1. Drop every source map (js, css, and the rtl-flipped css variants).
map_count=$(find "$DIST" -type f -name '*.map' | wc -l | tr -d ' ')
find "$DIST" -type f -name '*.map' -delete

# 2. Strip the trailing sourceMappingURL pragma so the browser stops asking for a
#    file that is now a 404. esbuild always emits it on its own final line — both
#    the js `//#` and the css `/*# ... */` form — so deleting whole matching lines
#    cannot eat bundle content. perl -ni is used over sed -i because the -i syntax
#    for sed differs between BSD (macOS) and GNU (Linux servers).
stripped=0
while IFS= read -r f; do
	if grep -qE '^[[:space:]]*/[*/]# sourceMappingURL=' "$f"; then
		perl -ni -e 'print unless m{^\s*/[*/]# sourceMappingURL=}' "$f"
		stripped=$((stripped + 1))
	fi
done < <(find "$DIST" -type f \( -name '*.js' -o -name '*.css' \))

echo "hardened: removed $map_count source map(s), stripped pragma from $stripped bundle(s)"

# 3. Fail loudly if anything slipped through, so a broken run is never silent.
if [ "$(find "$DIST" -type f -name '*.map' | wc -l | tr -d ' ')" != "0" ]; then
	echo "error: source maps still present under $DIST" >&2
	exit 1
fi
if grep -rlE '^[[:space:]]*/[*/]# sourceMappingURL=' "$DIST" >/dev/null 2>&1; then
	echo "error: sourceMappingURL pragma still present under $DIST" >&2
	exit 1
fi

echo "verified: no source maps and no sourceMappingURL pragmas remain"
