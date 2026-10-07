# NDS ERP Saudi — GitHub Codespaces

This repository is the authoritative Saudi NDS ERP source tree.

Create the environment from **GitHub → Code → Codespaces → Create codespace**.

The repository provides a reproducible Dev Container with Python 3.14, Node.js 24, Yarn 1.22, MariaDB 11.8, Redis, Bench 5.31.0, the Saudi app set, and automatic port forwarding to port 6000.

Production database dumps, site_config.json, private files, runtime environments, node_modules, and generated runtime state are intentionally not committed.

For an exact Saudi data restore, supply the exact database/files backup through Codespaces development-environment secrets. The bootstrap script restores them without requiring the project to exist on the local computer.

Normal design work should avoid bench update/migrations unless explicitly required. Change the minimum source, build affected assets, verify in-browser, then commit and push.
