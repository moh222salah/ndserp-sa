# Installation

## Requirements

- Frappe / ERPNext v15
- HRMS (`hrms`) for employee costs in Daily P&L
- Node.js 18+ and Yarn (for POS / KDS builds)

## Install into an existing bench

```bash
# From your bench directory
cd /path/to/frappe-bench

# Link this app (if not already under apps/)
bench get-app /home/frappe/nds-restaurant
# or: ln -s /home/frappe/nds-restaurant apps/nds_restaurant

bench --site yoursite.local install-app nds_restaurant
bench --site yoursite.local migrate
cd apps/nds_restaurant && yarn install && yarn build
bench --site yoursite.local build --app nds_restaurant
bench --site yoursite.local clear-cache
bench --site yoursite.local build-search-index
```

## Create a dedicated site (optional)

```bash
bench new-site nds.localhost --mariadb-root-password YOUR_ROOT_PASSWORD --admin-password admin
bench --site nds.localhost install-app erpnext hrms nds_restaurant
bench --site nds.localhost migrate
```

## Access

- Desk: `/app`
- POS: `/restaurant-pos`
- Kitchen Display: `/kotdisplay/<NDS Production Unit name>`

Continue with [docs/setup-guide.md](docs/setup-guide.md).
