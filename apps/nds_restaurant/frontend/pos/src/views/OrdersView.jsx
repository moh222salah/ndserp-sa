import React, { useState, useEffect } from "react";
import { usePOSStore } from "../store";
import { getOrders, markInvoicePrinted, changeOrderType, getInvoice, getPosContext } from "../api";

export default function OrdersView() {
  const { context, setView, setInvoice, setSelectedTable } = usePOSStore();
  const [orders, setOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [activeTab, setActiveTab] = useState("Unbilled");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 15000);
    return () => clearInterval(interval);
  }, [activeTab, context?.pos_profile]);

  async function loadOrders() {
    if (!context?.pos_profile) return;
    setLoading(true);
    try {
      const res = await fetch(
        `/api/method/nds_restaurant.api.pos.get_orders?pos_profile=${encodeURIComponent(
          context.pos_profile
        )}&status=${encodeURIComponent(activeTab)}`
      );
      const data = await res.json();
      const list = data.message || [];
      setOrders(list);
      if (selectedOrder) {
        const updated = list.find((o) => o.name === selectedOrder.name);
        if (updated) setSelectedOrder(updated);
      }
    } catch (e) {
      console.error("Failed to load orders", e);
    }
    setLoading(false);
  }

  async function handlePrint(order) {
    try {
      await fetch(
        `/api/method/nds_restaurant.api.pos.mark_invoice_printed?invoice=${encodeURIComponent(
          order.name
        )}`,
        {
          method: "POST",
          headers: {
            "X-Frappe-CSRF-Token": window.csrf_token || "",
          },
        }
      );

      const printFormat = context?.settings?.print_format || "NDS Receipt";
      const printUrl = `/api/method/frappe.utils.print_format.download_pdf?doctype=POS%20Invoice&name=${encodeURIComponent(
        order.name
      )}&format=${encodeURIComponent(printFormat)}&no_letterhead=1`;
      
      const printWindow = window.open(printUrl, "_blank");
      if (printWindow) {
        printWindow.focus();
      }

      loadOrders();
    } catch (e) {
      alert("Failed to mark printed");
    }
  }

  function handlePay(order) {
    try {
      setInvoice(order.name);
      
      usePOSStore.setState({
        cart: [{
          item: "invoice_total",
          item_name: "Order " + order.name,
          rate: order.grand_total,
          qty: 1,
        }],
      });

      if (order.restaurant_table) {
        setSelectedTable(order.restaurant_table);
      }
      
      setView("pay");
    } catch (e) {
      console.error("Failed to load invoice for payment", e);
    }
  }

  function handleOpenOrder(order) {
    setInvoice(order.name);
    if (order.restaurant_table) {
      setSelectedTable(order.restaurant_table);
    } else {
      setView("menu");
    }
  }

  const filteredOrders = orders.filter((o) => {
    const q = searchQuery.toLowerCase();
    return (
      o.name?.toLowerCase().includes(q) ||
      o.restaurant_table?.toLowerCase().includes(q) ||
      o.customer?.toLowerCase().includes(q)
    );
  });

  const tabs = ["Draft", "Unbilled", "Recently Paid", "Paid", "Consolidated", "Return"];

  return (
    <div className="flex h-full bg-nds-dark text-white">
      {/* Left List Panel */}
      <div className="w-1/2 border-r border-white/10 p-4 flex flex-col h-full">
        <h2 className="font-display text-xl mb-3">Orders</h2>

        {/* Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-2 mb-3">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setSelectedOrder(null);
              }}
              className={`px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition ${
                activeTab === tab
                  ? "bg-amber-500 text-black font-bold"
                  : "bg-white/5 hover:bg-white/10 text-gray-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Search Bar */}
        <input
          type="text"
          placeholder="Search invoice, table, or customer..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-black/20 border border-white/10 rounded px-3 py-2 text-sm text-white mb-3 focus:outline-none focus:border-amber-500"
        />

        {/* Orders List */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {loading && orders.length === 0 ? (
            <p className="text-center text-xs text-gray-400 py-8">Loading orders...</p>
          ) : filteredOrders.length === 0 ? (
            <p className="text-center text-xs text-gray-400 py-8">No orders found</p>
          ) : (
            filteredOrders.map((ord) => (
              <div
                key={ord.name}
                onClick={() => setSelectedOrder(ord)}
                className={`p-3 rounded-lg border cursor-pointer transition flex justify-between items-center ${
                  selectedOrder?.name === ord.name
                    ? "bg-amber-500/10 border-amber-500/50"
                    : "bg-black/20 border-white/5 hover:bg-white/5"
                }`}
              >
                <div>
                  <p className="text-sm font-bold text-white">{ord.name}</p>
                  <p className="text-xs text-gray-400">
                    {ord.restaurant_table ? `${ord.restaurant_table} · ` : ""}
                    {ord.custom_nds_order_type || "Take Away"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-emerald-400">
                    {ord.grand_total?.toFixed ? ord.grand_total.toFixed(2) : ord.grand_total}
                  </p>
                  <p className="text-xs text-gray-400">{ord.customer_name || ord.customer || "Walk-in"}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Detail Panel */}
      <div className="w-1/2 p-4 flex flex-col h-full bg-black/10">
        {selectedOrder ? (
          <div className="flex flex-col h-full justify-between">
            <div>
              <div className="border-b border-white/10 pb-3 mb-3">
                <h3 className="font-display text-lg text-white">{selectedOrder.name}</h3>
                <p className="text-xs text-gray-400 mb-2">
                  Customer: {selectedOrder.customer_name || selectedOrder.customer || "Walk-in"}
                </p>
                
                {/* --- P2-T8: Order Type & Table display with Edit Dropdown --- */}
                <div className="text-sm text-gray-300 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-400">
                      Type: {selectedOrder.custom_nds_order_type || "Take Away"}
                      {selectedOrder.restaurant_table && ` | Table: ${selectedOrder.restaurant_table}`}
                    </p>
                  </div>

                  {true && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">Edit Type:</span>
                      <select
                        value={selectedOrder.custom_nds_order_type || "Take Away"}
                        onChange={async (e) => {
                          try {
                            const newType = e.target.value;
                            const currentTable = selectedOrder.restaurant_table || selectedOrder.custom_nds_table;
                            
                       
                            await changeOrderType(selectedOrder.name, newType, currentTable);
                            
                         
                            const updatedTable = newType === "Take Away" ? null : currentTable;
                            setSelectedOrder({ 
                              ...selectedOrder, 
                              custom_nds_order_type: newType, 
                              restaurant_table: updatedTable,
                              custom_nds_table: updatedTable
                            });

                      
                            loadOrders();

                          
                            const profile = usePOSStore.getState().context?.pos_profile;
                            if (profile) {
                              const refreshedContext = await getPosContext(profile);
                              usePOSStore.getState().setContext(refreshedContext.message || refreshedContext);
                            }

                          } catch (err) {
                            alert("Failed to change order type. Ensure it is enabled in POS Profile.");
                          }
                        }}
                        className="bg-black/40 border border-white/20 text-xs rounded px-2 py-1 text-amber-400 focus:outline-none"
                      >
                        <option value="Dine In">Dine In</option>
                        <option value="Take Away">Take Away</option>
                        <option value="Delivery">Delivery</option>
                      </select>
                    </div>
                  )}
                </div>
                {/* ------------------------------------------------------------- */}
              </div>

              {/* Items List */}
              <div className="space-y-2 max-h-60 overflow-y-auto mb-4">
                {selectedOrder.items?.map((item, idx) => (
                  <div key={idx} className="flex justify-between text-sm bg-black/20 p-2 rounded">
                    <span>
                      {item.item_name} × {item.qty}
                    </span>
                    <span className="font-medium">{item.amount}</span>
                  </div>
                ))}
              </div>

              <div className="border-t border-white/10 pt-2 text-right text-lg font-bold">
                Total: {selectedOrder.grand_total} SAR
              </div>
            </div>

            {/* Actions Buttons */}
            <div className="flex gap-2 mt-4 pt-3 border-t border-white/10">
              <button
                onClick={() => handleOpenOrder(selectedOrder)}
                className="flex-1 py-2.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium transition"
              >
                Open
              </button>
              <button
                onClick={() => handlePrint(selectedOrder)}
                className="flex-1 py-2.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition"
              >
                Print
              </button>
              <button
                onClick={() => handlePay(selectedOrder)}
                className="flex-1 py-2.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition"
              >
                Pay
              </button>
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-gray-400 text-sm">
            Select an order to view details
          </div>
        )}
      </div>
    </div>
  );
}