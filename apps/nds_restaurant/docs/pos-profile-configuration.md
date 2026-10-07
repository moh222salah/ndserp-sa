# POS Profile Configuration

Critical NDS fields on **POS Profile**:

| Field | Purpose |
|-------|---------|
| Restaurant | Links to NDS Restaurant |
| KOT Naming Series | Required for KOT generation (`KOT-.#####`) |
| Role Allowed For Billing | Roles that can settle bills |
| View All Status | Show all invoice statuses |
| Paid Limit | Recently paid list size |
| Enable Discount | Allow discounts in POS |
| Table Attention Time | Minutes before table attention hint |
| Show Item Image | Menu thumbnails |
| KOT Warning Time | KDS late highlight (minutes) |
| KOT Audio Alert / Sound | Kitchen alert |
| Notify KOT Delay + Recipients | Delayed KOT notifications |
| Table / Parcel Order Printer | KOT print fallbacks |
| Enable QZ Print + QZ Host | Thermal printing via QZ Tray |
| Printer Settings | Bill/KOT network printers |
| Enable Multiple Cashier | Multi-cashier workflow |
| Applicable for Users → Main Cashier | Head cashier flag |

## Checklist

**Must have:** Company, Warehouse, Cost Center, Selling Price List, Payments, Restaurant, users, billing roles.

**Should have:** KOT Naming Series, View All Status, Paid Limit.
