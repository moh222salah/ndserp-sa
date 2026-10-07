import React, { useCallback, useEffect, useState } from "react";
import { usePOSStore } from "../store";
import { getInvoice, cancelOrder, changeOrderType, markKotPickedUp, openPrintUrl, reprintKot, settleAggregator } from "../api";
import { printBill } from "../lib/print";
import { parseErrorMessage, showUserAlert } from "../lib/errors";
import TransferPanel from "./TransferPanel";

function money(v) {
  return Number(v || 0).toFixed(2);
}

export default function OrderDetail({ invoiceName, onClose, onChanged, onSelectOrder }) {
  const { context, openInvoice, refreshContext } = usePOSStore();
  const [details, setDetails] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showTransfer, setShowTransfer] = useState(false);
  const printFormat = context?.settings?.print_format || "NDS Receipt";
  const editOrderType = !!context?.settings?.edit_order_type;

  const load = useCallback(async () => {
    try {
      const res = await getInvoice(invoiceName);
      setDetails(res?.message || res);
      setError("");
    } catch (e) {
      setDetails(null);
      setError(parseErrorMessage(e));
    }
  }, [invoiceName]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(fn) {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      showUserAlert(parseErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const handlePrint = () =>
    run(async () => {
      const printed = await printBill(details.name, printFormat);
      if (printed?.printed) showUserAlert(`Bill sent to ${printed.printer}`, "green");
      await load();
      onChanged && onChanged();
    });

  const handleReprintKot = (kotName) =>
    run(async () => {
      const res = await reprintKot(kotName);
      const data = res?.message || res || {};
      if (data.printed) {
        showUserAlert(`KOT ${kotName} reprinted on ${data.printer} (${data.kot})`, "green");
      } else {
        if (data.print_url) openPrintUrl(data.print_url);
        showUserAlert(`Duplicate ${data.kot} sent to the kitchen display`, "green");
      }
      await load();
    });

  const handlePickedUp = (kotName) =>
    run(async () => {
      await markKotPickedUp(kotName);
      showUserAlert(`KOT ${kotName} picked up`, "green");
      await load();
      onChanged && onChanged();
    });

  const handleOpen = () => openInvoice(details, "menu");

  // P8-T2: settle a draft aggregator order per the Branch settings
  const handleSettleAggregator = async () => {
    setBusy(true);
    try {
      const res = await settleAggregator(details.name);
      const out = res?.message || res;
      showUserAlert(out.keep_unpaid ? `Unpaid invoice ${out.sales_invoice} created` : `Settled with ${out.mode_of_payment}`, "green");
      onChanged && onChanged();
      if (out.keep_unpaid) onClose && onClose();
      else load();
      refreshContext();
    } catch (e) {
      showUserAlert(parseErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const handlePay = () => {
    openInvoice(details, "pay");
  };

  const handleCancel = () =>
    run(async () => {
      const label = details.docstatus === 1 ? "Cancel paid invoice" : "Void order";
      const reason = window.prompt(`${label} ${details.name}? Enter a reason:`, "");
      if (reason === null) return;
      const res = await cancelOrder(details.name, reason);
      const data = res?.message || res;
      showUserAlert(data?.action === "voided" ? `Order ${details.name} voided` : `Invoice ${details.name} cancelled`, "green");
      await refreshContext();
      onChanged && onChanged();
      if (data?.action === "voided") {
        onClose();
      } else {
        await load();
      }
    });

  const handleTransferDone = async (data) => {
    setShowTransfer(false);
    await refreshContext();
    onChanged && onChanged();
    if (data?.merged_from && data?.invoice && data.invoice !== details.name) {
      if (onSelectOrder) onSelectOrder(data.invoice);
      else onClose();
      return;
    }
    await load();
  };

  const handleTypeChange = (newType) =>
    run(async () => {
      await changeOrderType(details.name, newType, details.table);
      await refreshContext();
      await load();
      onChanged && onChanged();
    });

  if (error) {
    return (
      <aside className="w-96 shrink-0 border-l border-white/10 p-5 bg-black/20 flex flex-col">
        <div className="flex justify-end">
          <button onClick={onClose} className="text-nds-muted hover:text-white">✕</button>
        </div>
        <p className="text-red-300 text-sm">{error}</p>
      </aside>
    );
  }

  if (!details) {
    return (
      <aside className="w-96 shrink-0 border-l border-white/10 p-5 bg-black/20 flex items-center justify-center text-nds-muted">
        Loading details…
      </aside>
    );
  }

  const isDraft = details.docstatus === 0;
  const needsPrint = isDraft && context?.settings?.print_before_pay && details.order_type === "Dine In" && details.table && !details.invoice_printed;

  return (
    <aside className="w-80 xl:w-96 shrink-0 min-w-0 border-l border-white/10 p-4 xl:p-5 bg-black/20 flex flex-col overflow-y-auto overflow-x-hidden" data-testid="order-detail">
      <div className="flex justify-between items-start mb-3">
        <div className="min-w-0">
          <h3 className="font-display text-xl truncate">
            {details.daily_order_no ? (
              <span className="text-nds-accent mr-2" data-testid="detail-order-no">
                #{details.daily_order_no}
              </span>
            ) : null}
            {details.name}
          </h3>
          <p className="text-nds-muted text-sm">
            {details.order_status}
            {details.table ? ` · ${details.table}` : ""}
            {details.posting_time ? ` · ${String(details.posting_time).slice(0, 5)}` : ""}
          </p>
        </div>
        <button onClick={onClose} className="text-nds-muted hover:text-white">✕</button>
      </div>

      <div className="text-sm mb-3 pb-3 border-b border-white/10 space-y-1">
        {details.aggregator ? (
          <div className="flex justify-between">
            <span className="text-nds-muted">Aggregator</span>
            <span className="px-1.5 rounded bg-orange-500/20 text-orange-200" data-testid="detail-aggregator">
              {details.aggregator_name || details.aggregator}
              {details.aggregator_order_id ? ` #${details.aggregator_order_id}` : ""}
            </span>
          </div>
        ) : null}
        <Row label="Customer" value={details.customer_name || details.customer} />
        <Row label="Captain" value={details.captain} />
        {details.cashier && <Row label="Cashier" value={details.cashier} />}
        <div className="flex justify-between items-center">
          <span className="text-nds-muted">Type</span>
          {isDraft && editOrderType && details.can_edit && !details.aggregator ? (
            <select
              value={details.order_type || "Dine In"}
              disabled={busy}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="bg-black/40 border border-white/20 text-xs rounded px-2 py-1"
            >
              <option value="Dine In">Dine In</option>
              <option value="Take Away">Take Away</option>
              <option value="Delivery">Delivery</option>
            </select>
          ) : (
            <span>{details.order_type || "Take Away"}</span>
          )}
        </div>
        {details.custom_order_comments && <Row label="Comments" value={details.custom_order_comments} />}
      </div>

      <div className="flex-1 overflow-auto space-y-1 mb-3">
        {(details.items || []).map((item, idx) => (
          <div key={idx} className={`flex justify-between text-sm ${item.is_addon ? "pl-4 text-nds-muted" : ""}`}>
            <span className="min-w-0">
              {item.is_addon ? "+ " : ""}
              {item.qty}× {item.item_name}
              {item.notes ? <span className="block text-xs italic text-nds-muted">{item.notes}</span> : null}
            </span>
            <span>{money(item.amount ?? item.qty * item.rate)}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-white/10 pt-3 mb-3 text-sm space-y-1">
        <Row label="Net" value={money(details.net_total)} />
        {Number(details.total_taxes_and_charges) ? <Row label="Tax" value={money(details.total_taxes_and_charges)} /> : null}
        {Number(details.discount_amount) ? <Row label="Discount" value={`-${money(details.discount_amount)}`} /> : null}
        <div className="flex justify-between font-display text-xl pt-1">
          <span>Total</span>
          <span>{money(details.rounded_total || details.grand_total)}</span>
        </div>
      </div>

      <div className="mb-3 pb-3 border-b border-white/10 text-sm" data-testid="order-payments">
        <p className="mb-1 text-xs uppercase tracking-wide text-nds-muted">Payments</p>
        {(details.payments || []).length ? (
          <>
            {details.payments.map((p) => (
              <Row key={p.mode_of_payment} label={p.mode_of_payment} value={money(p.amount)} />
            ))}
            <Row label="Paid" value={money(details.paid_amount)} />
          </>
        ) : (
          <p className="text-nds-muted">No payments yet</p>
        )}
      </div>

      {(details.kots || []).length > 0 && (
        <div className="mb-3 text-xs text-nds-muted">
          <p className="mb-1 uppercase tracking-wide">KOTs</p>
          {details.kots.map((k) => (
            <div key={k.name} className="flex items-center justify-between gap-2 py-0.5" data-testid="kot-row">
              <span>
                {k.name} · {k.kot_type}
                {k.docstatus === 2 ? " (cancelled)" : ""}
                {k.docstatus === 1 && (k.order_status || k.served) ? (
                  <span
                    className={`ml-1 px-1.5 py-0.5 rounded text-[10px] ${
                      (k.order_status || (k.served ? "Served" : "")) === "Served"
                        ? "bg-emerald-600 text-white"
                        : k.order_status === "Picked Up"
                        ? "bg-white/20 text-white"
                        : "bg-amber-500 text-black"
                    }`}
                    data-testid="kot-status"
                  >
                    {k.order_status || "Served"}
                    {k.production_time != null && k.order_status !== "Ready For Prepare" ? ` · ${k.production_time}m` : ""}
                  </span>
                ) : null}
              </span>
              <span className="flex gap-1">
              {k.can_pick_up ? (
                <button
                  disabled={busy}
                  onClick={() => handlePickedUp(k.name)}
                  className="px-2 py-0.5 rounded bg-emerald-600 hover:bg-emerald-500 text-[11px] text-white"
                  data-testid="kot-picked-up"
                >
                  Picked Up
                </button>
              ) : null}
              {details.can_reprint_kot && k.docstatus === 1 && k.kot_type !== "Duplicate" ? (
                <button
                  disabled={busy}
                  onClick={() => handleReprintKot(k.name)}
                  className="px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-[11px] text-white"
                  data-testid="kot-reprint"
                >
                  Reprint
                </button>
              ) : null}
              </span>
            </div>
          ))}
        </div>
      )}

      {showTransfer && isDraft && (
        <TransferPanel
          invoice={details.name}
          expectedModified={details.modified}
          onDone={handleTransferDone}
          onCancel={() => setShowTransfer(false)}
        />
      )}

      {needsPrint && <p className="mb-2 text-xs text-amber-300">Print the bill before payment.</p>}

      <div className="grid grid-cols-2 gap-2">
        {isDraft && details.can_edit ? (
          <button disabled={busy} onClick={handleOpen} className="py-2 rounded bg-white/10 hover:bg-white/20 text-sm">
            Open
          </button>
        ) : null}
        <button disabled={busy} onClick={handlePrint} className="py-2 rounded bg-blue-600 hover:bg-blue-500 text-sm">
          {isDraft ? "Print bill" : "Reprint"}
        </button>
        {isDraft && details.can_pay ? (
          <button
            disabled={busy || needsPrint}
            onClick={handlePay}
            className="py-2 rounded bg-nds-accent text-nds-green text-sm font-medium disabled:opacity-40"
            title={needsPrint ? "Please print invoice before making payment" : ""}
          >
            Pay
          </button>
        ) : null}
        {isDraft && details.can_pay && details.aggregator ? (
          <button
            disabled={busy}
            onClick={handleSettleAggregator}
            data-testid="detail-aggregator-settle"
            className="py-2 rounded bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium"
          >
            Settle (aggregator)
          </button>
        ) : null}
        {isDraft && details.can_transfer ? (
          <button
            disabled={busy}
            onClick={() => setShowTransfer((v) => !v)}
            className="py-2 rounded bg-white/10 hover:bg-white/20 text-sm"
            data-testid="transfer-button"
          >
            Transfer
          </button>
        ) : null}
        {details.can_cancel ? (
          <button disabled={busy} onClick={handleCancel} className="py-2 rounded bg-red-700/80 hover:bg-red-600 text-sm">
            {isDraft ? "Void" : "Cancel invoice"}
          </button>
        ) : null}
      </div>
    </aside>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-nds-muted">{label}</span>
      <span className="text-right truncate">{value}</span>
    </div>
  );
}
