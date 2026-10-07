# Architecture & Implementation Plan

## Phase 1 — Environment note (honest)

This codebase was authored against **ERPNext v16** (officially stable since
2026-01-12; current line ~v16.32.x). It could **not** be installed, migrated,
or UI-verified from the authoring environment because there is no live Frappe
bench / ERPNext site there. All `bench` inspection, install, migrate, seed and
UI-verification steps in the original brief must run on your bench. Where the
brief said "inspect field X from the installed system," this document gives you
the exact snippet to run instead of guessing.

## 1. ERPNext functionality reused (never duplicated)

| Concern | ERPNext DocType used via Link |
|--------|-------------------------------|
| Legal entity | Company |
| Fuel products | Item (+ Item Group, Item Price) |
| Stock location | Warehouse |
| Costing | Cost Center |
| POS session | POS Profile → POS Opening/Closing Entry |
| Sale of fuel | Sales Invoice (is_pos) / POS Invoice |
| Money in | Payment Entry |
| Fuel received (commercial) | Purchase Receipt / Stock Entry |
| People | User / Employee |
| Tax & currency | Taxes, Currency (SAR), Price List |

The Gas Station app owns **only** station-specific operational data.

## 2. New Gas Station DocTypes

**Configuration (Phase 2 — done):** Gas Station, PTS Controller,
Gas Station Pump, Gas Station Nozzle (child), Gas Station Tank,
Gas Station Probe.

**Current state (Phase 4):** Pump State, Tank State, Controller Connection
State — one row per equipment, updated in place, so dashboards never scan
history.

**History / append-only (Phase 4):** PTS Pump Transaction, Tank Measurement,
Tank Delivery, Station Alert, Integration Event. Never overwritten. Indexed on
their PTS identifiers, station, equipment and datetime.

**Rules / dev (Phase 5, 7):** Alert Rule, Mock PTS Controller,
Reconciliation Run + result rows.

## 3. Integration endpoints (Phase 3)

Whitelisted REST methods under `gas_station.api.pts`, one per jsonPTS
operation: `UploadPumpTransaction`, `UploadTankMeasurement`,
`UploadInTankDelivery`, `UploadAlertRecord`, `UploadStatus`,
`UploadConfiguration`. Each dispatches to a handler
(`PumpTransactionHandler`, …) behind a `PTSIntegrationProvider` abstraction
with `RealPTSProvider` and `MockPTSProvider` implementations that share the
same normalized handlers.

## 4. Data flow

```
PTS-2 / Mock ── jsonPTS ──► endpoint ──► authenticate + JSON-schema validate
   ──► identify controller/station ──► dedupe (unique index on packet/txn id)
   ──► persist raw Integration Event ──► ACK immediately
   ──► enqueue background job ──► normalize ──► update Current State
   ──► map to ERPNext (POS/Sales/Stock) ──► realtime push ──► dashboard
```

Receiving is separated from ERPNext business processing: the PTS request is
ACKed as soon as the raw event is persisted and de-duplicated; expensive
ERPNext work runs in a background job with retry, so a PTS transaction is never
lost on ERPNext failure.

## 5. Idempotency

Database-level uniqueness (not just Python checks) on the composite of
`pts_controller` + `pts_packet_id` and on `pts_transaction_id`, enforced with
unique indexes on the history DocTypes. Retried packets resolve to
`Duplicate`, never a second business record.

## 6. Demo strategy

Every demo record carries `is_demo = 1`. `seed_demo_data()` drives the Mock
provider through the real handlers (no fake dashboard rows), producing coherent
data: pump totalizers increase monotonically; tank balance obeys
`opening + deliveries − dispensed ± adjustments ≈ closing`; ERPNext sales match
processed PTS transactions — with a few intentional mismatches so reconciliation
screens show real exceptions. `reset_demo_data()` deletes only `is_demo = 1`
records.

## 7. Risks / assumptions

1. **ERPNext field names** — verified only for stable masters; POS/Sales/Stock
   mapping (Phase 6) must be confirmed against your v16 site (see *Verify*).
2. **POS vs plain Sales Invoice** — mapping target (POS Invoice vs
   `Sales Invoice.is_pos`) depends on your POS setup; decided in Phase 6.
3. **Physical delivery ≠ commercial purchase** — Tank Delivery is a physical
   event; it is *linked* to, never auto-creates, a Purchase Receipt.
4. **Real PTS-2 auth** (HMAC vs token) depends on your controller config;
   both paths are stubbed in Phase 3.

## Verify (run on your v16 bench, paste output back before Phase 6)

```bash
bench --site yoursite version
bench --site yoursite console
```
```python
import frappe, json
for dt in ["POS Profile","POS Invoice","Sales Invoice","POS Opening Entry",
           "POS Closing Entry","Payment Entry","Purchase Receipt","Item Price"]:
    meta = frappe.get_meta(dt)
    print("\n==", dt, "==")
    print(json.dumps([f.fieldname for f in meta.fields if f.reqd], indent=0))
```
