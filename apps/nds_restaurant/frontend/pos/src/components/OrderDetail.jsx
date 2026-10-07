import React, { useEffect, useState } from "react";
import { printInvoice, markInvoicePrinted } from "../api";

export default function OrderDetail({ order, onClose, onOpen, onPay }) {
  const [details, setDetails] = useState(null);

  useEffect(() => {
    frappe.client.get("POS Invoice", order.name).then(res => {
      setDetails(res);
    });
  }, [order.name]);

  const handlePrint = async () => {
    try {
      await markInvoicePrinted(details.name);
      printInvoice(details.name, details.print_format || "NDS Receipt");
      onClose();
    } catch (e) {
      console.error(e);
    }
  };

  if (!details) {
    return (
      <aside className="w-80 shrink-0 border-l border-white/10 p-5 bg-black/20 flex items-center justify-center text-nds-muted">
        Loading details...
      </aside>
    );
  }

  return (
    <aside className="w-80 shrink-0 border-l border-white/10 p-5 bg-black/20 flex flex-col overflow-y-auto">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-display text-xl">{details.name}</h3>
          <p className="text-nds-muted text-sm">
            {details.custom_nds_order_type} {details.custom_nds_table ? `· ${details.custom_nds_table}` : ''}
          </p>
        </div>
        <button onClick={onClose} className="text-nds-muted hover:text-white">✕</button>
      </div>

      <div className="text-sm mb-4 pb-4 border-b border-white/10">
        <div className="flex justify-between mb-1">
          <span className="text-nds-muted">Customer</span>
          <span>{details.customer}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-nds-muted">Status</span>
          <span>{details.status}</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto space-y-2 mb-4">
        {details.items.map(item => (
          <div key={item.name} className="flex justify-between text-sm">
            <span>{item.qty}x {item.item_name}</span>
            <span>{item.amount.toFixed(2)}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-white/10 pt-4 mb-4">
        <div className="flex justify-between font-display text-xl">
          <span>Total</span>
          <span>{details.grand_total.toFixed(2)}</span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {details.docstatus === 0 && (
          <>
            <button onClick={onOpen} className="w-full py-2 rounded bg-white/10 hover:bg-white/20 text-sm">
              Open in Menu
            </button>
            <button onClick={onPay} className="w-full py-2 rounded bg-nds-accent text-nds-green text-sm font-medium">
              Pay
            </button>
          </>
        )}
        <button 
          onClick={handlePrint} 
          className="w-full py-2 rounded bg-white/10 hover:bg-white/20 text-sm"
        >
          Print
        </button>
      </div>
    </aside>
  );
}