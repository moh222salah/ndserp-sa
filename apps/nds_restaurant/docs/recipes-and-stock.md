# Recipes & Stock Tracking

## Approach 1 — No recipe

- Non-stock item: always available  
- Stock item: availability = warehouse qty; ERPNext deducts on submit  

## Approach 2 — NDS Recipe (recommended for prepared food)

1. Raw material Items with Maintain Stock  
2. Material Receipt into POS warehouse  
3. Buying Price List for COGS  
4. **NDS Recipe**: menu item → ingredients + qty per portion  

### POS behavior

- Availability badge = min floor(stock / qty) across ingredients  
- Draft invoices reserve ingredient demand  
- On payment: Material Issue Stock Entry; linked on invoice as Recipe Stock Entry  
- On cancel: stock entry cancelled  

Do **not** use ERPNext BOM for POS availability — only NDS Recipe drives badges and auto deduction.
