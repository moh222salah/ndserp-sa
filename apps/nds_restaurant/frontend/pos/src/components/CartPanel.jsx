import React from "react";
import CustomerPicker from "./CustomerPicker";

export default function CartPanel({
  cart,
  total,
  comments,
  setComments,
  updateQty,
  onSend,
  onPay,
  full,
  orderType,
  onPlaceAndPay,
}) {
  return (
    <aside className={`${full ? "w-full" : "w-72 shrink-0"} border-l border-white/10 p-4 bg-black/20 flex flex-col`}>
      <h3 className="font-display text-lg mb-3">Order</h3>

      <CustomerPicker />

      <div className="flex-1 overflow-auto space-y-2">
        {cart.length === 0 && <p className="text-nds-muted text-sm">Cart is empty</p>}
        {cart.map((c) => {
          const isAddon = c.is_addon;
          const lineKey = c.line_id || c.item;
          return (
            <div key={lineKey} className={`flex items-center gap-2 text-sm ${isAddon ? "ml-4 opacity-80" : ""}`}>
              {!isAddon && c.image && (
                <img
                  src={encodeURI(c.image)}
                  alt=""
                  className="w-10 h-10 object-cover rounded shrink-0"
                  onError={(e) => {
                    e.target.style.display = "none";
                  }}
                />
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate">
                  {isAddon && <span className="text-nds-accent mr-1">+</span>}
                  {c.item_name}
                </div>
                {c.notes && <div className="text-xs text-nds-muted italic truncate">{c.notes}</div>}
                <div className="text-nds-muted">{c.rate}</div>
              </div>
              {!isAddon && (
                <div className="flex items-center gap-1 shrink-0">
                  <button className="w-6 h-6 rounded bg-white/10" onClick={() => updateQty(lineKey, c.qty - 1)}>
                    −
                  </button>
                  <span className="w-6 text-center">{c.qty}</span>
                  <button className="w-6 h-6 rounded bg-white/10" onClick={() => updateQty(lineKey, c.qty + 1)}>
                    +
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <textarea
        className="mt-3 w-full rounded bg-white/5 border border-white/10 p-2 text-sm"
        rows={2}
        placeholder="Order comments"
        value={comments}
        onChange={(e) => setComments(e.target.value)}
      />
      <div className="mt-3 font-display text-xl">Total {total.toFixed(2)}</div>
      <div className="mt-3 flex gap-2">
        {orderType === "Take Away" ? (
          <button onClick={onPlaceAndPay} className="flex-1 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium">
            Place & Pay
          </button>
        ) : (
          <>
            <button onClick={onSend} className="flex-1 py-2 rounded bg-white/15 hover:bg-white/25 text-sm">
              Send KOT
            </button>
            <button onClick={onPay} className="flex-1 py-2 rounded bg-nds-accent text-nds-green text-sm font-medium">
              Pay
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
