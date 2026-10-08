# NDS ERP Saudi — GitHub Codespaces

This repository is the authoritative Saudi NDS ERP source tree.

## Browser-only development

Use **GitHub → Code → Codespaces → Create codespace on main**.

The Dev Container prepares the Saudi stack automatically:

- Python 3.14
- Node.js 24
- Yarn 1.22.22
- Frappe Bench 5.31.0
- MariaDB 11.8
- Redis
- All 17 Saudi apps listed in `bench/apps.txt`
- Frappe application on port 8080
- Persistent Codespace supervisor that restarts `bench start` when port 8080 stops responding
- Socket.IO on 9000
- File watcher on 6787

After the container is created or resumed, the startup supervisor launches the ERP with:

`bench start`

The supervisor keeps checking `http://127.0.0.1:8080/login` and restarts the Bench process when it exits or the HTTP endpoint goes down. Port 8080 is forwarded automatically by Codespaces.

GitHub Codespaces can still suspend an idle/stopped Codespace according to its account or organization policy; the supervisor resumes automatically when the container starts again.

and verifies:

`http://127.0.0.1:8080/login`

GitHub Codespaces browser access uses the forwarded port URL supplied by Codespaces; `127.0.0.1:8080` is the loopback address inside the Codespace container.

## Exact Saudi data restore

Production database dumps, `site_config.json`, private files, runtime environments, node_modules, and generated runtime state are intentionally not committed.

For an exact Saudi data restore, define these Codespaces development-environment secrets:

- `NDSERP_SITE_CONFIG_JSON`
- `NDSERP_DB_DUMP_URL` pointing to the exact Saudi `.sql.gz`
- `NDSERP_FILES_ARCHIVE_URL` pointing to the exact Saudi site-files `.tar.gz`

When the database dump secret is present, the bootstrap creates the database/user, restores the dump, and does **not** run `install-app` or `migrate` afterward, preserving the restored database state.

Without production-data secrets, the Codespace creates a clean Saudi development site and installs the complete source app set.

## Change-control boundary

Egyptian ERP is out of scope for this repository. Work here is Saudi-only.

Normal UI/design work should avoid migrations, database writes, authentication changes, and unrelated business-logic changes unless explicitly requested. Make the minimum source change, build the affected assets, verify, then commit and push.
