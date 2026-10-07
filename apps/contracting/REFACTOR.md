# Architecture Refactor — status

Pivot per Change Requests 01–09 (uploaded). The app moves from a Contract-centric
model to a **Project-only** model with **Budget BOQ Item** as the operational BOQ.

## Confirmed decisions
- Project is the single root; **Construction Contract DocType is retired** (baseline → Project custom fields).
- **Budget BOQ Item replaces Contract BOQ Item** as the golden record. No Contract BOQ DocType.
- Tender Subcontract: Supplier present but **optional**.
- **WIP Cost + Cost Adjustment are dropped** (new model = Budget vs Actual from source docs).
- IPC valuation engine kept, but re-pointed (Project + Budget BOQ Item, Unit = text, no Measurement/Valuation Method).
- Tender BOQ import = BOQ No + Description + Quantity + CSI Code only (no values at import).
- Deduction Type kept (used by IPC).
- Unit = free text everywhere (no UOM/Measurement/Valuation Method masters).

## Removed/retired (per CRs) — destructive phase, pending data decision
Construction Contract, Contract BOQ Item, Construction Resource, Resource Rate,
Measurement Method, Valuation Method, Cost Category, Item Work,
Construction Allocation Rule, Construction Cost Allocation (+Detail),
Actual Cost Event, WIP Cost (+Line), Cost Adjustment, Tender Version (as DocType).

## Added
CSI Code (tree), Budget (+ Budget BOQ Item + 5 cost tables), Budget Per Cost Code (+ item),
Project custom fields, WBS account overrides, Construction Settings dimension toggles,
custom fields on ERPNext source docs (Stock Entry / Purchase Invoice / Salary Slip /
Expense Claim / Journal Entry / Subcontract IPC), 2 cost-control reports.

## Phase status
- [x] **Phase 1 — Foundation (additive, safe):** CSI Code tree; Project custom fields
      (contract baseline + default accounts) via after_install; WBS default-account
      overrides; Construction Settings dimension toggles (Enable Cost Code / WBS / BOQ Item).
- [x] **Phase 2 — Budget core (additive):** Project Budget + Budget BOQ Item (standalone, +5 cost tables, Cost+Selling views, Unit text, CSI link) + Budget Per Cost Code (+item, leaf+dup validation). Old Construction Budget removed.
- [x] **Phase 3 — Tender refactor:** Tender BOQ Item refactored (BOQ No/Desc/Qty/Unit text/CSI + pricing modes + 5 cost tables Material/Labour/Equipment/Expense/Subcontract); Tender header summary + markup; removed Tender Version/Resource/Pricing DocTypes; create_budget_from_tender() method; Excel import via Frappe Data Import on Tender BOQ Item.
- [x] **Phase 4 — Destructive removals + repoint (DONE, clean refactor):** retired 15 DocTypes (Construction Contract, Contract BOQ Item, Construction Resource, Resource Rate, Measurement/Valuation Method, Cost Category, Item Work, Construction Allocation Rule, Construction Cost Allocation +Detail, Actual Cost Event, WIP Cost +Line, Cost Adjustment) + cost_allocation_service + cost_adapters; repointed 25 DocTypes (Contract→Project, Contract BOQ Item→Budget BOQ Item, uom Link→unit text, dropped item_work/measurement_method/valuation_method/cost_category); variation engine now recomputes Project.current_contract_value; EOT→Project; reports/workspace/tests updated.
- [x] **Phase 5 — Execution repoint (done in Phase 4):** Executed Quantity / Operation Measurement / WBS Allocation now use Project + Budget BOQ Item + Unit text.
- [x] **Phase 6 — Cost capture:** ct_cost_code / ct_wbs / ct_boq_item custom fields added to Purchase Invoice Item, Stock Entry Detail, Journal Entry Account, Expense Claim, Salary Slip (+ native on Subcontract IPC) via setup_cost_dimension_fields; actual cost read from posted source docs (services/actual_cost.py), no allocation document.
- [x] **Phase 7 — IPC & commercial repoint (done in Phase 4):** Client/Subcontract IPC, Final Account, Closeout, Variations/Claims/EOT/Amendment all on Project + Budget BOQ Item.
- [x] **Phase 8 — Reports:** Cost Code Budget vs Actual + BOQ Budget vs Actual (read actual from source docs, variance %); workspace/translations/tests updated.

## Pending decision (gates Phase 4)
Is there real data on the live site to preserve (→ migration patches), or is it still
test data (→ clean refactor)? Needed before the destructive phase only.


## Polish (added)
- [x] Settings-driven show/hide of ct_cost_code / ct_wbs / ct_boq_item on Purchase Invoice, Stock Entry, Journal Entry, Expense Claim, Salary Slip, Subcontract IPC (public/js/*.js + doctype_js hooks; reads Construction Settings toggles).
- [x] Tender "Create Project Budget" action button (Approved/Awarded) → calls create_budget_from_tender and opens the new budget.
