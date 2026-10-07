# Implementation Plan

Derived from the approved design set (ERD, Final DocType Architecture, Field-by-
Field Specification, Frappe Implementation Specification, Technical Build
Specification, Integration Review). Build order follows the dependency order the
docs agree on.

| Phase | Scope | Depends on confirmed legacy rules? | Status |
|------|-------|-----------------------------------|--------|
| **1** | App foundation + Setup masters + Contract/BOQ + WBS/WBS Allocation | No | **Built (this package)** |
| 2 | Tender → Tender Version → Tender BOQ → Resources → Indirect Cost → Pricing | No | **Built** |
| 3 | Variations, Claims, EOT, Amendments (+ current-value engine) | No | **Built** |
| 4 | Executed Quantity (full) + Operation Measurement (structure + proposed value model) | Partly (arithmetic + Part Type/Period to confirm) | **Built (confirm formula)** |
| 5 | Procurement: Material Requirement, Procurement Plan (ERPNext ordered/received adapters later) | Partly | **Built (core)** |
| 6 | Subcontract, Subcontract BOQ, Mapping, Subcontract Variation (Measurement/IPC → engine phase) | Partly | **Built (core)** |
| 7 | Client IPC + Subcontract IPC + shared valuation engine | Assumed model (see ASSUMPTIONS.md) | **Built** |
| 8 | Cost Allocation + Actual Cost Event + ERPNext adapters (PI/JE/Stock/Subcontract IPC) | Assumed capture basis | **Built** |
| 9 | WIP Cost + Cost Adjustment (assumed formula, see ASSUMPTIONS.md) | Assumed formula | **Built** |
| 10 | Cost Budget + Lines (structure; Commitment/Forecast need cost phases) | No | **Built (structure)** |
| 11 | Final Account (+lines) + Contract Closeout (+checklist gates) | No | **Built** |
| 12 | 16 Roles + Permission matrix + Workflows (via idempotent after_install) | No | **Built** |
| 13 | Reports: BOQ Status, Client/Subcontract IPC Register, Variation Register, Cost Control Summary | No | **Built (core set)** |
| 14 | Test suite (measurement formula, baseline, IPC P+C=Total, allocation balance) | Alongside each phase | **Built (core set)** |

## Cross-cutting engineering rules (applied every phase)

- Server-side logic is authoritative; JS never carries a financial control.
- Approved/posted records are immutable; correction = cancel/reverse/adjust.
- Every source-derived record keeps `Source Type + Source Document + Source
  Item` and a deterministic unique key → idempotent, retry-safe integration.
- Calculations live in `contracting/services/*`, not in controllers.
- Approved valuation documents snapshot rate/account/currency/rules so later
  master changes never alter history.
- `Item Work` is **never** a stored Cost Allocation dimension — always derived
  via `Contract BOQ Item → Item Work`.
