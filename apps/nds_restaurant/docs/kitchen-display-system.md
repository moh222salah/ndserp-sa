# Kitchen Display System (KDS)

## Flow

1. Order placed in POS  
2. `kot_execute()` groups items by Item Group  
3. Groups map to **NDS Production Unit**  
4. One **NDS KOT** per unit (New / Modified / Partially Cancelled / Cancelled)  
5. KDS at `/kotdisplay/<Production Unit>` shows cards in realtime (polling + socket)

## Card colors

- White — new dine-in  
- Blue — takeaway/delivery  
- Orange — modified  
- Red — cancelled / partial cancel  

## Actions

- Click card → Serve (or Confirm Cancel)  
- Warning time from POS Profile highlights late KOTs  

## Setup

1. Plan kitchen stations  
2. Create Production Units with Item Groups  
3. Optional printers on the unit  
4. Open KDS URL on kitchen screens  
