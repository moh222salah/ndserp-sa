<h1 align="center"> NDS ERP Theme v16</h1>

<p align="center">
  A bilingual (Arabic / English) enterprise theme for <strong>ERPNext v16</strong> and
  <strong>Frappe Framework v16</strong>.
</p>

<p align="center">
  <img alt="ERPNext v16" src="https://img.shields.io/badge/ERPNext-v16-0089ff">
  <img alt="Frappe v16" src="https://img.shields.io/badge/Frappe-v16-71a5f7">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green">
</p>

---

## What it does

- **Desk launcher** rebuilt as a card grid: one card per app, a line glyph and a
  bottom accent bar in that module's own colour, hover / active / keyboard-focus
  states, and a responsive 6 / 5 / 4 / 3 / 2 column ladder.
- **Docked status bar** showing system status, last login and server. Every cell
  is hidden when its data is genuinely unavailable — nothing is invented.
- **Full RTL support**, including a mirrored child-table editor, correct bidi
  isolation for Latin runs inside Arabic text, and Arabic-aware type scaling.
- **Self-hosted Arabic typography** — IBM Plex Sans Arabic with real
  400/500/600/700 cuts. No CDN, no external request, works on an air-gapped
  deployment.
- **Workspace rail** with translated labels, grouped by owning app, and a
  one-click Arabic ⇄ English switch.
- **Branded login page** driven by a `Login Page Settings` doctype (bilingual
  fields, logo, colours, social links).
- **Enterprise background system**: gradient, ambient lighting and ~1% film
  grain. Pure CSS — no images, no canvas, no JavaScript, no animation.
- **Light and dark themes**, both contrast-checked.

## Requirements

| | |
|---|---|
| Frappe Framework | v16 |
| ERPNext | v16 |
| Python | 3.14 |
| Node | 24 |

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/Amirmansi/Eng-Amir-Theme_V16.git
bench --site your-site.local install-app amir_theme_v16
bench build --app amir_theme_v16
bench --site your-site.local clear-cache
```

For production, build minified assets:

```bash
bench build --app amir_theme_v16 --production
```

## Uninstall

```bash
bench --site your-site.local uninstall-app amir_theme_v16
bench remove-app amir_theme_v16
```

The app owns one doctype (`Login Page Settings`) and no business data, so
removing it cannot affect transactions.

## Design principles

**Zero core modification.** The app touches ERPNext and Frappe only through
supported extension points — `app_include_css`, `app_include_js`,
`web_include_*`, `extend_bootinfo`, and its own doctype. There is no monkey
patching, no overridden framework method and no edited core file, so upgrades
stay safe.

**No unnecessary dependencies.** Frappe v16 already ships Lucide (~1,780 icons
inlined into the desk document) and `@popperjs`. This theme reuses them rather
than bundling an icon library or a positioning library of its own. The only
third-party asset added is the Arabic font.

**Presentation layer only.** No route, permission, API or business rule is
modified.

## Architecture

```
amir_theme_v16/
├─ boot.py                  extend_bootinfo — adds last_login for the status bar
├─ hooks.py                 the entire integration surface
├─ api/language.py          whitelisted Arabic ⇄ English switch
├─ amir_theme/doctype/      Login Page Settings
├─ translations/ar.csv      ~10,800 Arabic strings
└─ public/
   ├─ fonts/                IBM Plex Sans Arabic (Arabic subset, 4 weights)
   ├─ js/core/              desk_host · desk_launcher · desk_statusbar · login_brand
   └─ scss/
      ├─ abstracts/         design tokens, module colour + icon map
      ├─ base/              @font-face
      ├─ components/        status bar
      ├─ layouts/           desk launcher
      ├─ themes/            light / dark tokens, background system
      └─ _legacy.scss       pre-restructure rules, dismantled module by module
```

`_legacy.scss` is append-forbidden: it may only shrink as components are
extracted into `components/` and `layouts/`.

## Credits and licence

MIT — see [`license.txt`](license.txt).

This app began as a rename-in-place fork of
[**Saas Theme** by CommitStreet](https://github.com/vineyrawat/saas_theme) (MIT)
and retains that copyright notice as the licence requires. The desk launcher,
status bar, background system, Arabic typography, translation layer, login
branding and SCSS architecture were written for this app.

Bundled font: **IBM Plex Sans Arabic** © IBM Corp.,
[SIL OFL 1.1](https://scripts.sil.org/OFL) — see
[`LICENSE.txt`](amir_theme_v16/public/fonts/ibm-plex-sans-arabic/LICENSE.txt).

Icons are Frappe's bundled [Lucide](https://lucide.dev) set (ISC), referenced
from the sprite Frappe already inlines — not redistributed here.
