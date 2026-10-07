# Architecture

The `optical` app is a vertical layer over ERPNext. ERPNext stays the source of truth for Company,
Customer, Item, Warehouse, Selling, Buying, Stock and Accounting; the app adds the optical domain,
job workflow and print formats.

## Standard ERPNext vs custom
| Concern | ERPNext | Optical app |
|---|---|---|
| Customer, Supplier, Company | Standard | Optical Profile (1:1 with Customer, name == customer) |
| Products | Item (+ custom fields, Optical Details section) | none |
| Invoicing / payment / tax / stock | Sales Invoice (update_stock), Payment Entry | Optical Order builds the invoices |
| Branch | Cost Center + Warehouse pair (no HRMS dependency) | fields on order/job; restrict with User Permissions |
| Purchasing external lab work | Purchase Order | Optical Job creates it |
| Optical data, workflow, QC, remake, warranty, insurance | n/a | custom DocTypes |

## Layers
- `optical/optical/doctype/*`: DocTypes + controllers (validation, actions).
- `optical/utils/*`: pure logic (insurance split, stage flow, optics validation) and print helpers exposed to Jinja.
- `optical/events/*`: Sales Invoice and Payment Entry hooks keep the order payment status in sync.
- `optical/setup/*`: roles, role profiles, Item custom fields, service items (idempotent, also run on migrate).
- `optical/api.py`: whitelisted helpers used by form scripts.
- AI is intentionally not coupled to the app. Add it as a separate app that reads Optical Prescription / Optical Order.

## Insurance accounting default (changeable)
The insurer is an ERPNext Customer created with the Insurance Company. The customer invoice carries a
discount equal to the insurer's share (customer pays only their portion); the insurer's share is a
separate Sales Invoice to the insurer customer, so normal receivable aging and payment entries apply.
When the insurer invoice is fully paid the Insurance Claim becomes Settled automatically.
