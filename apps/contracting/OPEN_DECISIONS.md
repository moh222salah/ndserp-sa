# Open Decisions — status

## Resolved (applied)
- **Measurement order** = Supply -> Installation -> Pass. Implemented in
  `services/measurement_service.py`.
- **IPC legacy fields dropped**: `ValCashed`, `Pricing`, `Entry`, `Main` will
  NOT be created on the IPC DocTypes (Phase 7).

## Still needed before the engines are correct

### A. Measurement value arithmetic (Phase 4 — a model is in place, confirm it)
A concrete model is already coded and isolated in one function
(`compute_item_value`). Confirm or correct this single formula:

    completion = supply_split% * supply_progress%  +  install_split% * install_progress%
    value      = qty * unit_price * completion * pass%

1. Is Supply/Installation **additive** (shares of the rate that sum to 100%, as
   above) or a **sequential multiply**?
2. **Part Type** — what does each measurement Part mean and how does it feed
   value? (Currently captured but not driving value.)
3. **Period Per Days** — its formula / role in the value. (Currently captured
   only.)

### B. IPC Valuation & Deduction Engine (Phase 7 — still blocked)
4. **Deduction application order** when Storage, Temporary, Item, Header, Output
   Tax, Withholding, Advance Recovery and Insurance coexist. (Not yet provided.)
5. **Storage** sign and formula — add to or hold back certified value, and how
   cumulative previous storage is carried. (Not yet provided.)
6. Snapshot fields to freeze at IPC approval (Previous must come from last
   approved IPC).
7. Does an approved Client IPC auto-create the Sales Invoice or only make it
   eligible? Same for Subcontract IPC -> Purchase Invoice.

### C. Cost Adjustment (Phase 9 — still blocked)
8. Exact Cost Adjustment formula and meaning of `Qty_UnderCont`, `Qty_CostCont`,
   `Qty_Adj` (+ value counterparts). (Not yet provided.)

### D. Workflow / platform
9. Legacy `Confirm1..Confirm6` -> workflow states/roles mapping.
10. Multi-company: code uniqueness per-company or global?
11. Cost Position generation mode + allocation-rule precedence + unallocated
    cost handling (Phase 8).

## Legacy-name reminders
- `Ct_PO_m` = Subcontractor Measurement; `Ct_OpPO_m` = Operation Measurement
  ("Operation" = ERPNext Project).
