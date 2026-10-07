# Gas Station — Operations & PTS-2 Integration for ERPNext v16

A custom Frappe app that turns ERPNext v16 into a live gas-station operations
platform: it ingests PTS-2 forecourt telemetry (via jsonPTS), keeps current
equipment state and full history, drives ERPNext sales/stock, raises alerts,
reconciles physical vs. financial figures, and ships a realtime dashboard plus a
Mock PTS simulator for demos and testing.

> **Design rule:** ERPNext is the business/financial system of record. This app
> **reuses** ERPNext (Company, Item, Warehouse, Cost Center, POS Profile, Sales
> Invoice, Payment Entry, Purchase Receipt) and never duplicates it. It only adds
> the forecourt/telemetry layer ERPNext doesn't have.

---

## ⚠️ Read this first

This code was written to be install-ready but has **not been run against a live
v16 bench** during authoring. Install it, run `migrate`, and report errors. The
two spots most likely to need a tweak on your bench are called out explicitly:

1. **POS / Sales Invoice field names** (`erpnext_integration/mapping.py`). Sales
   Invoice fields are stable across v15/v16, but confirm your POS Profile and
   walk-in customer setup before enabling auto-invoicing.
2. **Workspace schema** (`setup/install.py::_build_workspace`). Workspace JSON has
   shifted between Frappe versions, so the workspace is created **in code, wrapped
   in try/except**, and can never break `migrate`. If it doesn't render perfectly,
   everything else still works and you reach features via the awesomebar.

---

## Install

```bash
cd frappe-bench
bench get-app gas_station /path/to/gas_station
bench --site <site> install-app gas_station
bench --site <site> migrate
bench restart
```

`after_install` creates the five roles, default Alert Rules, Gas Station Settings,
and the workspace. `after_migrate` (idempotent) also creates the composite unique
indexes that enforce idempotency at the DB level.

## Seed the demo (recommended first run)

```bash
bench --site <site> execute gas_station.demo.seed.seed_demo_data
# optional: --kwargs "{'days':5,'txns_per_day':40}"
```

Creates a SAR demo company (**Saudi Demo Fuel Operations**), fuel Items with SAR
Item Prices, five Saudi stations (Riyadh North, Jeddah Corniche, Dammam Port,
Mecca Road, Medina Gate) with pumps/nozzles/tanks/probes/controllers, then drives
the **Mock PTS provider through the real integration pipeline** to generate several
days of transactions, tank measurements, deliveries, alerts, and a few
intentional reconciliation mismatches.

Remove it with `bench --site <site> execute gas_station.demo.seed.reset_demo_data`.

Then open **Gas Station Dashboard** from the awesomebar or the workspace.

## Live simulator (continuous demo)

Open a **Mock PTS Controller**, click **Start Simulator**. The scheduled `tick`
job emits due packets every minute for running mocks. Use the toolbar to generate
one-off Transactions / Measurements / Alerts / Deliveries, or to simulate
connection loss/restore. All of it flows through the same endpoints as real data.

---

## PTS ingestion endpoints (jsonPTS)

A physical controller POSTs JSON (no Frappe session); requests are authenticated
inside the pipeline by controller credentials and an optional HMAC signature
(`X-PTS-Signature` header, validated against the controller's `hmac_secret`).

| Operation | Endpoint (`/api/method/…`) |
|---|---|
| Pump transaction | `gas_station.gas_station.api.upload_pump_transaction` |
| Tank measurement | `gas_station.gas_station.api.upload_tank_measurement` |
| In-tank delivery | `gas_station.gas_station.api.upload_in_tank_delivery` |
| Alert record | `gas_station.gas_station.api.upload_alert_record` |
| Status / heartbeat | `gas_station.gas_station.api.upload_status` |
| Configuration | `gas_station.gas_station.api.upload_configuration` |
| Generic (operation in body) | `gas_station.gas_station.api.upload` |

**Normalized envelope** every provider produces and `dispatch.receive` consumes:

```json
{
  "controller": "CTRL-RYD-N",
  "operation": "UploadPumpTransaction",
  "packet_id": "…",
  "data": { "transaction_id": "…", "pump": "1", "nozzle": "1",
            "volume": 40.0, "price": 2.33, "amount": 93.2, "total_volume": 1040.0 }
}
```

`RealPTSProvider.parse_raw()` maps a raw jsonPTS packet to this envelope — fill it
against your controller's exact protocol; everything downstream is unchanged.

---

## Pipeline (same path for Mock and Real)

```
provider ──envelope──▶ dispatch.receive
  1 record Integration Event (raw, always)
  2 validate schema
  3 identify controller + verify credentials/HMAC
  4 dedupe (controller + transaction/delivery id)   ← DB unique index backs this
  5 handler.persist  → history doctype
  6 handler.update_state → current-state doctype (fast)
  7 mark controller seen + connection state
  8 ACK  ◀── returned to controller now
  9 enqueue business processing (ERPNext) in the background
```

ACK is separated from ERPNext work, so a PTS transaction is **never lost** if
invoicing fails. Missing sensor values stay `None` (shown as “—”), never coerced
to `0`.

## ERPNext mapping

| Physical event (this app) | ERPNext (reused) |
|---|---|
| PTS Pump Transaction | POS **Sales Invoice** (+ cash Payment, optional stock update) |
| Nozzle → `erpnext_item` | **Item** |
| Tank / Station warehouse | **Warehouse** |
| Station | **Company** / **Cost Center** / **POS Profile** |
| Tank Delivery | link a **Purchase Receipt** manually (physical ≠ commercial) |

Auto-invoicing is off by default. Turn it on in **Gas Station Settings** after
setting a walk-in **Customer** and selling **Price List**.

## Reconciliation

**Reconciliation Run** (or the reports) compares: PTS transaction amount vs linked
Sales Invoice `grand_total`; summed transaction volume vs pump totalizer delta;
and tank opening + deliveries − dispensed vs sensor closing volume.

## Reports (13, Script Reports)

Pump Performance · Nozzle Performance · Fuel Dispensing · Tank Level History ·
Tank Variance · Tank Delivery Report · PTS Transaction Report ·
PTS vs ERPNext Reconciliation · Pump Totalizer Reconciliation ·
Station Alerts Report · Integration Events Report · Controller Connectivity
Report · Station Operational Summary.

---

## Data model

**Config:** Gas Station · PTS Controller · Gas Station Pump (+ Nozzle child) ·
Gas Station Tank · Gas Station Probe · Alert Rule · Gas Station Settings (single).
**Current state (one row/equipment):** Pump State · Tank State · Controller
Connection State. **History (append-only):** PTS Pump Transaction · Tank
Measurement · Tank Delivery · Station Alert · Integration Event. **Simulator:**
Mock PTS Controller. **Reconciliation:** Reconciliation Run (+ Result child).

## Roles

Gas Station Administrator · Gas Station Integration Manager · Station Manager ·
Station Operator · Gas Station Viewer.

## Tests

```bash
bench --site <site> run-tests --app gas_station \
  --module gas_station.gas_station.tests.test_integration
```

Covers: normal transaction, duplicate rejection, unknown controller, malformed
payload, tank-state update, missing-value-stays-None, alert creation, raw event
logging, mock-uses-same-pipeline, and reconciliation flagging.

## Scheduler jobs

- `integration.watchdog.mark_stale_controllers` — flags Stale/Offline when packets stop.
- `simulator.engine.tick` — emits due packets for running Mock PTS Controllers only.
