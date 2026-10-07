# Aggregator orders (P8)

Delivery platforms (Talabat, HungerStation, Jahez, …) are configured per **Branch**.

## Setup

1. Create a **Customer** for each platform (e.g. "Talabat").
2. Optionally create a selling **Price List** for it and add **Item Prices** for the menu items. Items without a price there keep their menu rate.
3. Open **Branch → Aggregator Settings** and add a row:
   - **Customer** (required).
   - **Price List** (optional).
   - **Mode of Payment**: used when *Keep Unpaid* is off. A Bank/General mode whose account is the platform's clearing account works well. Without one, the POS Profile's default mode is used.
   - **Keep Sales Invoice Unpaid**: the order becomes an unpaid **Sales Invoice** for the platform customer, to be settled later with a Payment Entry.
   - **Create Invoice without Tax**: no tax template or tax rows on the order.
4. Optional: **NDS Restaurant → Aggregator Series Prefix** (e.g. `AGG`) names aggregator POS orders `AGG-26-00001` when the POS Profile has *Use Invoice Series Prefix* on.

## POS

1. The header shows one orange button per platform. Picking one sets the order type to **Aggregator** and locks the customer. Menu prices switch to the platform's price list.
2. Type the platform's order reference in **Platform order ID** (shown on KOTs, the KDS card, the receipt and in Orders).
3. **Send KOT** keeps the order as a draft. **Place & Settle** / **Place (unpaid)** sends it to the kitchen and settles it:
   - *Keep Unpaid off*: the POS Invoice is submitted as Paid with the row's mode of payment.
   - *Keep Unpaid on*: a receivable Sales Invoice is created (same items, `update_stock`, recipe ingredients issued) and the draft POS order is removed. The kitchen keeps its tickets, which now link to the Sales Invoice (`NDS KOT.sales_invoice`).
4. Drafts can also be settled later from **Orders → order → Settle (aggregator)**.

## Visibility

- **Orders**: one filter chip per platform; an orange "Talabat #id" badge on each order; the **Aggregator Unpaid** tab (billing users) lists the unpaid aggregator Sales Invoices and opens them in Desk.
- **KDS**: an orange "Talabat #id" tag on the card.
- **Receipt** (NDS Receipt): "Talabat #id" under the order type.

Invoice fields: `custom_nds_order_type = Aggregator`, `custom_aggregator` (Customer), `custom_aggregator_order_id`. Sales Invoice: `custom_source_pos_invoice`, `custom_aggregator`, `custom_aggregator_order_id`, `custom_daily_order_no`, `custom_recipe_stock_entry`.
