# ASSUMPTIONS — read before trusting any calculated figure

The legacy formulas below were not confirmed; the owner asked to proceed with
best-judgment defaults. Each is the **standard construction-industry model**,
each lives in **one isolated function**, and each is listed here so you can
verify against your legacy system and change a single line. **None of these are
"confirmed correct" — treat every computed money figure as provisional until
you validate it against real historical documents.**

## 1. Operation Measurement value  (`services/measurement_service.py`)
Adopted: **additive** supply/installation split (NOT sequential multiply).

    supply_split%   = BOQ.supply_percent
    install_split%  = BOQ.installation_percent, or (100 - supply_split) if blank
    supply_prog%    = measurement Supply %   (default 100)
    install_prog%   = measurement Installation %  (default 100)
    completion      = supply_split% * supply_prog%  +  install_split% * install_prog%
    pass_factor     = Pass % / 100  (only if Allow Pass; else 1.0)
    value           = qty * unit_price * completion * pass_factor

- **Measurement Part `Type` / `Period Per Days`**: adopted as **informational
  only** — captured, not driving certified value. If they should modify value,
  give the rule and it goes into this one function.

## 2. IPC valuation & deductions  (`services/ipc_valuation_service.py`)
Shared by Client IPC and Subcontract IPC. Adopted order:

    work_done  = Σ(current_qty * unit_price)
    storage    = Σ storage_value                 # materials on site: ADDS (sign +)
    gross_val  = work_done + storage
    − temporary deductions (item)
    − item deductions (item)
    − header deductions (percentage on gross_val, else entered)
    = subtotal
    − retention%        * work_done
    − advance_recovery% * work_done
    − insurance%        * work_done
    = net_before_tax
    + output_tax%       * net_before_tax          # VAT: ADDS
    − withholding_tax%  * net_before_tax          # WHT: DEDUCTS
    = net_current
    Previous = Σ net_current of prior Approved/Posted IPCs (same contract/subcontract)
    Total    = Previous + net_current

- **Storage sign** adopted as **positive (adds to the amount due)** — materials
  delivered/on-site increase this period's certificate.
- **Dropped fields** (per instruction): `ValCashed`, `Pricing`, `Entry`, `Main`.
- **Posting**: an approved IPC is marked eligible; it does **not auto-create**
  the Sales/Purchase Invoice (a `sales_invoice` / `purchase_invoice` link is
  provided to attach it). Change if you want auto-posting.

## 3. Cost Adjustment  (`Cost Adjustment` controller)
Adopted WIP cost-matching model:

    Qty_Adj          = Qty_UnderCont − Qty_CostCont
    unit_cost        = approved allocated actual cost / Qty_CostCont   (if blank)
    Adjustment_Value = Qty_Adj * unit_cost

Meaning adopted: `Qty_UnderCont` = executed/certified qty attributable to the
BOQ line; `Qty_CostCont` = qty for which actual cost has been allocated; the
adjustment accrues/defers cost so recognised cost matches progress.

## 4. Cost capture & allocation  (`integrations/cost_adapters.py`)
- ERPNext **Purchase Invoice / Journal Entry / Stock Entry** on submit, and
  **Subcontract IPC** when Posted, create an idempotent **Actual Cost Event**
  (deduped by `unique_key = "<SourceType>:<name>"`).
- Events are **Unallocated** until a **Construction Cost Allocation** spreads
  them across dimensions; PI amount taken as `base_net_total`. Adjust the amount
  basis / trigger events per your accounting policy.

## 5. Other adopted defaults
- Over-execution control = **Warning** (non-blocking). Make it Block via policy.
- Measurement/period "Previous" always sourced from prior **Approved** docs.
- Multi-company: single-company code space assumed (`field:code` naming).
