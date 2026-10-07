# Fonts

## Why self-hosted rather than the Google Fonts CDN
- Works on an air-gapped / intranet ERP deployment.
- No third-party request per page load; no client IP disclosed to Google.
- One fewer DNS + TLS handshake on first paint.
- Immune to CDN outages or regional blocking.

## Why IBM Plex Sans Arabic
- SIL OFL 1.1 — permissive, commercial use allowed.
- Maintained by IBM (github.com/IBM/plex), active project.
- Ships REAL 400/500/600/700 Arabic cuts. The system fallback on macOS
  exposes only two states, so any "bold" was a synthesised smear.
- Metrically designed to sit beside a Latin sans, which is what Inter is.

## Why Latin is NOT bundled
Frappe already ships InterVariable. Bundling a second Latin family would
duplicate framework functionality and add bytes for no gain.
