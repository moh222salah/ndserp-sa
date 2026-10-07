# Contracting — Enterprise Construction / Contracting App for ERPNext v16

A custom Frappe app that adds construction business logic **on top of** ERPNext.
ERPNext remains the system of record for finance, stock, buying, selling,
HR/payroll and assets. This app owns construction truth: tender, contract, BOQ,
WBS, execution, measurement, IPC certification, cost allocation, WIP and
final account / closeout.

> **Core principle**
> ERPNext owns Financial & Operational ERP truth — the Contracting App owns
> Construction Business truth. **Contract BOQ Item is the Golden Record.**

---

## What is in this package (Phase 1 — Foundation)

This is the installable foundation. It contains **no** logic that depends on
the legacy formulas the design flagged as "confirm before coding", so it is
safe to install and build on now.

**Module: Contracting Setup** (11 masters)
Construction Settings (Single), Item Work (tree), Cost Category, Cost Code
(tree), Construction Resource, Resource Rate, Measurement Method, Valuation
Method, Deduction Type, Deduction Rule, Construction Allocation Rule.

**Module: Contracting Commercial**
Construction Contract, Contract BOQ Item (**Golden Record**, a standalone
DocType so every downstream document can `Link` to it).

**Module: Contracting Execution**
WBS (tree), WBS Allocation.

Each transactional DocType ships with a server-side controller enforcing the
architecture's non-negotiable rules (baseline immutability, Project/Contract/
BOQ context consistency, hierarchy/cycle checks, derived amounts).

**Module: Contracting Tender** (Phase 2)
Tender, Tender Version (with Indirect Cost lines), Tender BOQ Item (standalone,
with a per-line Resource build-up), Tender Resource, Tender Indirect Cost,
Tender Pricing (transparent Estimated Cost → Overhead/Risk → Commercial
Adjustment → Profit → Tender Price rollup).

**Contracting Commercial — changes** (Phase 3)
Contract Variation (+ items), Contract Claim (+ items), Extension of Time,
Contract Amendment (+ items). Approving a Variation drives the **current-value
engine** (`contracting/services/variation_engine.py`): it recomputes each
Contract BOQ Item's `current_qty / current_rate / current_amount` from the
immutable baseline plus approved variation deltas — idempotent by construction,
so reject/cancel/delete cleanly reverses. New-Item variation lines create the
BOQ line on approval. EOT updates the contract end date on approval and never
touches value; Claims feed the Final Account, not the BOQ baseline.

**Module: Contracting Procurement** (Phase 5 — core)
Construction Material Requirement (+ items) and Procurement Plan (+ items).
Requirements and plans are tied to Project / WBS / Contract BOQ Item with
context validation. ERPNext Buying (PO / Receipt) and Stock (Stock Entry) are
**reused, not rebuilt**; the ordered/received/issued quantities on the plan are
filled by ERPNext adapters in a later phase, and the derived `remaining_qty`
stays consistent meanwhile.

**Module: Contracting Subcontract** (Phase 6 — commercial core)
Subcontract, Subcontract BOQ Item (standalone), Subcontract BOQ Mapping
(many-to-many bridge between client and subcontract BOQ lines), Subcontract
Variation (+ items). Baseline immutability and a subcontract value engine
(`contracting/services/subcontract_engine.py`) mirror the client side:
`current_value = original + approved variation values`, idempotent. **Subcontract
Measurement and Subcontract IPC are deferred to the engine phase** because they
share the blocked measurement/valuation logic.

**Module: Contracting Cost** (Phase 10 — structure)
Construction Budget (+ lines) carrying the full construction dimension set
(Project / Contract / WBS / BOQ Item / Cost Code / Cost Category / Account) with
budget qty/rate/amount and a derived total. Budget-vs-Commitment-vs-Actual-vs-
WIP-vs-Forecast reporting arrives with the cost phases (8/9), which need actual
and WIP data.

**Roles, permissions & workflows** (Phase 12)
`after_install` (in `contracting/setup/install.py`) provisions, idempotently:
- **16 roles** (Contracting Administrator, Contracts Manager, Estimation
  Engineer, Commercial Manager, Quantity Surveyor, Project Manager, Site
  Engineer, Procurement Officer, Subcontracts Manager, Cost Controller, Planning
  Engineer, Accounts User, Document Controller, Contracting User, Reviewer,
  Auditor);
- a **module-based permission matrix** applied as additive Custom DocPerms
  (re-runnable safely);
- **workflows** for Construction Contract, Contract Variation, Tender and
  Subcontract that drive each doctype's existing `status` field (Draft → Review →
  Approved → … ), with per-transition role gating.

Because it is idempotent and existence-checked, it can be re-run after adding
later-phase doctypes with `bench execute contracting.setup.install.after_install`.

**Contracting Execution — measurement** (Phase 4)
Executed Quantity (physical execution with Project/WBS/Contract/BOQ context
checks and a cumulative over-execution warning) and Operation Measurement
(+ items, + parts, + deductions) with Previous/Current/Total accumulation from
prior approved measurements. The item value is computed in
`contracting/services/measurement_service.py` using a **proposed standard model**
(additive supply/installation split × measured progress × pass), applied in the
confirmed order Supply → Installation → Pass. **Measurement Part (Type / Period
Per Days) is captured but does not yet drive value** pending its legacy
definition — see `OPEN_DECISIONS.md` item A.

**Module: Contracting IPC** (Phase 7)
Client IPC and Subcontract IPC (+ items, + shared header-deduction child) sharing
one valuation engine (`contracting/services/ipc_valuation_service.py`):
work done + storage → deductions → retention/advance/insurance → tax → net, with
Previous/Current/Total from prior approved certificates. Legacy fields
`ValCashed/Pricing/Entry/Main` were dropped per instruction.

**Contracting Cost — allocation, WIP, adjustment** (Phases 8–9)
Actual Cost Event (idempotent capture from ERPNext), Construction Cost Allocation
(+ detail) spreading events across dimensions, WIP Cost (+ lines) and Cost
Adjustment. ERPNext adapters (`contracting/integrations/cost_adapters.py`, wired
in `hooks.py`) turn Purchase Invoice / Journal Entry / Stock Entry / Subcontract
IPC into Actual Cost Events.

> **The value formulas in Phases 4, 7, 8 and 9 are documented ASSUMPTIONS, not
> confirmed legacy logic. Read `ASSUMPTIONS.md` and validate every money figure
> before relying on it.** Each formula is isolated in one function for one-line
> correction.

**Contracting Commercial — closeout** (Phase 11)
Final Account (pulls Original + Approved Variations + Approved Claims − Applicable
Deductions = Final Contract Value, plus certified/retention/advance position from
Client IPCs, and auto-builds BOQ snapshot lines) and Contract Closeout (default
checklist with mandatory gates; closing the checklist sets the contract to
Closed only when every mandatory item is done).

**Reports** (Phase 13) — script reports under each module's `report/` folder:
Contract BOQ Status, Client IPC Register, Subcontract IPC Register, Variation
Register, Cost Control Summary (Budget vs Actual/WIP).

**Tests** (Phase 14) — `contracting/tests/test_engines.py`: measurement formula
cases, baseline-immutability home, IPC Previous+Current=Total field guarantees,
and cost-allocation balance fields. Run with
`bench --site <site> run-tests --app contracting`.

See `IMPLEMENTATION_PLAN.md` for the full phase roadmap and
`OPEN_DECISIONS.md` for the items that must be confirmed before the
calculation-heavy phases (Measurement, IPC, Cost Adjustment).

---

## Install

Requires a working Frappe/ERPNext **v16** bench and site.

```bash
# from your bench directory
bench get-app contracting /path/to/contracting     # or: git clone into apps/
bench --site your.site install-app contracting
bench --site your.site migrate
bench build && bench restart
```

After install you will find the three modules in the Desk. Create your
Construction Settings, then Item Work / Cost Code trees, then a Construction
Contract and its Contract BOQ Items.

---

## Design decisions baked into Phase 1

- **Contract BOQ Item is a standalone DocType**, not a child table, because the
  architecture requires many documents to `Link` to individual BOQ lines
  (WBS Allocation, Executed Quantity, Measurement, IPC, Subcontract mapping,
  Cost Allocation). Child-table rows cannot be the target of a Link selector.
- **Reserved-name safety**: fields that would collide with Frappe internals are
  renamed (`work_name`, `parent_boq_item`, `parent_wbs`, `wbs_name`, etc.).
- **`current_*` fields are read-only** on Contract BOQ Item and are driven by
  approved changes; on first entry they mirror the immutable `original_*`
  baseline.
- **Permissions in metadata are limited to System Manager** so a clean install
  never fails on a not-yet-created custom role. The full 16-role matrix from the
  Frappe Implementation Specification is applied as fixtures in the roles phase.
- **Multi-company**: masters are Company-scoped; `field:code` naming assumes a
  single-company code space for now (flagged in `OPEN_DECISIONS.md`).

## Demo / seed data

Load Saudi construction demo data (idempotent) across every table:

```bash
bench --site your.site execute contracting.setup.seed.run
```

Creates 4 projects (Riyadh Tower, Jeddah Corniche Mall, Dammam Industrial
Warehouse, Makkah Grand Hotel), each with Tender, Project Budget + Budget BOQ,
Budget Per Cost Code, WBS + allocations, Executed Quantity, Operation
Measurement, Client IPC, a Subcontract chain (BOQ, mapping, variation, IPC),
Contract Variation/Claim/EOT/Amendment, Material Requirement, Procurement Plan,
Final Account, Closeout, plus shared masters (CSI Code tree, Cost Code tree,
Deduction Types, customers, subcontractors, items) and best-effort Journal
Entries carrying cost dimensions for the Budget-vs-Actual reports.
