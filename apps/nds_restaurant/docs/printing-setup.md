# Printing Setup

## Bill printing

- Network printers via POS Profile / Room **Printer Settings** (Bill checked)  
- Or QZ Tray: Enable QZ Print + QZ Host on POS Profile  

## KOT printing

Resolution order:

1. Production Unit printers (KOT checked; respect Block Takeaway KOT)  
2. Room printers  
3. POS Profile table/parcel printer fields  

## CUPS

Install CUPS, add printers, create **Network Printer Settings** in ERPNext, link in NDS.

## QZ

Install [QZ Tray](https://qz.io/download/) on the client; set host to `localhost` or the machine’s LAN IP.
