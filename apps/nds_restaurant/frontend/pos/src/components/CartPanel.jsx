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
  canBill = true,
  sentItems = [],
  canRemoveItems = true,
  aggregator = null,
  aggregatorOrderId = "",
  setAggregatorOrderId = () => {},
}) {
  // P4-T5: quantities already sent to the kitchen are locked unless removal is allowed.
  const keyOf = (item, notes, group) => `${item}|${notes || ""}|${group || ""}`;
  const sentByKey = {};
  (sentItems || []).forEach((s) => {
    const k = keyOf(s.item_code, s.notes, s.addon_group_id);
    sentByKey[k] = (sentByKey[k] || 0) + Number(s.qty || 0);
  });
  const cartByKey = {};
  cart.forEach((c) => {
    const k = keyOf(c.item, c.notes, c.is_addon ? c.addon_group_id : "");
    cartByKey[k] = (cartByKey[k] || 0) + Number(c.qty || 0);
  });
  return (
    <aside className={`${full ? "w-full" : "w-64 xl:w-72 shrink-0"} min-w-0 max-w-full border-l border-white/10 p-3 xl:p-4 bg-black/20 flex flex-col overflow-y-auto overflow-x-hidden`}>
      <h3 className="font-display text-lg mb-3">Order</h3>

      {aggregator ? (
        <div className="mb-3 rounded border border-orange-400/40 bg-orange-500/10 p-2 text-sm" data-testid="aggregator-panel">
          <div className="font-medium text-orange-200">{aggregator.customer_name || aggregator.customer}</div>
          <div className="text-xs text-nds-muted">
            {aggregator.price_list ? `${aggregator.price_list} · ` : ""}
            {aggregator.without_tax ? "No tax · " : ""}
            {aggregator.keep_unpaid ? "Keep unpaid" : `Pay: ${aggregator.mode_of_payment || "default"}`}
          </div>
          <input
            type="text"
            value={aggregatorOrderId}
            onChange={(e) => setAggregatorOrderId(e.target.value)}
            placeholder="Platform order ID"
            data-testid="aggregator-order-id"
            className="mt-2 w-full rounded bg-black/30 border border-white/10 px-2 py-1 text-sm"
          />
        </div>
      ) : (
        <CustomerPicker />
      )}

      <div className="flex-1 overflow-auto space-y-2">
        {cart.length === 0 && <p className="text-nds-muted text-sm">Cart is empty</p>}
        {cart.map((c) => {
          const isAddon = c.is_addon;
          const lineKey = c.line_id || c.item;
          const sentKey = keyOf(c.item, c.notes, isAddon ? c.addon_group_id : "");
          const sentQty = sentByKey[sentKey] || 0;
          const minusLocked = !canRemoveItems && sentQty > 0 && (cartByKey[sentKey] || 0) <= sentQty;
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
                <div className="text-nds-muted">
                  {c.rate}
                  {sentQty > 0 && (
                    <span className="ml-2 text-[11px] text-amber-300" title="Already sent to the kitchen" data-testid="sent-lock">
                      {canRemoveItems ? "" : "🔒 "}
                      {sentQty} sent
                    </span>
                  )}
                </div>
              </div>
              {!isAddon && (
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    className="w-6 h-6 rounded bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                    disabled={minusLocked}
                    title={minusLocked ? "Items already sent to kitchen cannot be removed" : ""}
                    onClick={() => updateQty(lineKey, c.qty - 1)}
                  >
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
        {orderType === "Aggregator" && aggregator && canBill ? (
          <>
            <button onClick={onSend} className="flex-1 py-2 rounded bg-white/15 hover:bg-white/25 text-sm">
              Send KOT
            </button>
            <button
              onClick={onPlaceAndPay}
              data-testid="aggregator-settle"
              className="flex-1 py-2 rounded bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium"
            >
              {aggregator.keep_unpaid ? "Place (unpaid)" : "Place & Settle"}
            </button>
          </>
        ) : orderType === "Take Away" && canBill ? (
          <button onClick={onPlaceAndPay} className="flex-1 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium">
            Place & Pay
          </button>
        ) : (
          <>
            <button onClick={onSend} className="flex-1 py-2 rounded bg-white/15 hover:bg-white/25 text-sm">
              Send KOT
            </button>
            {canBill && (
              <button onClick={onPay} className="flex-1 py-2 rounded bg-nds-accent text-nds-green text-sm font-medium">
                Pay
              </button>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
