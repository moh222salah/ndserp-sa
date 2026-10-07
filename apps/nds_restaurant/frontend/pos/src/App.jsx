import QzStatus from "./components/QzStatus";
import OpeningDialog from "./components/OpeningDialog";
import CloseShiftDialog from "./components/CloseShiftDialog";
import { useEffect, useState } from "react";
import { usePOSStore } from "./store";
import { parseErrorMessage, showUserAlert } from "./lib/errors";
import {
  getPosContext,
  getInvoice,
  createOrUpdateOrder,
  submitPayment,
  settleTakeaway,
  settleAggregator,
} from "./api";
import { printBill } from "./lib/print";

import CartPanel from "./components/CartPanel";
import MenuView from "./views/MenuView";
import PayView from "./views/PayView";
import OrdersView from "./views/OrdersView";
import ProductDialog from "./components/ProductDialog";
import FloorPlan from "./components/FloorPlan";

function cartLinePayload(c) {
  return {
    item_code: c.item,
    qty: c.qty,
    rate: c.rate,
    notes: c.notes || "",
    is_addon: c.is_addon || false,
    addon_group_id: c.addon_group_id || "",
    course: c.course || null,
  };
}

export default function App() {
  const {
    context,
    loading,
    error,
    view,
    selectedTable,
    orderType,
    courseFilter,
    cart,
    invoice,
    expectedModified,
    invoiceGrandTotal,
    invoicePrinted,
    setInvoicePrinted,
    cartDirty,
    comments,
    lastInvoice,
    setContext,
    setLoading,
    setError,
    setView,
    setOrderType,
    setCourseFilter,
    addToCart,
    updateQty,
    clearCart,
    setInvoice,
    setComments,
    setLastInvoice,
    cartTotal,
    customer,
    applySavedOrder,
    refreshContext,
    sentItems,
    aggregator,
    aggregatorOrderId,
    setAggregator,
    setAggregatorOrderId,
  } = usePOSStore();

  const [dialogItem, setDialogItem] = useState(null);
  const [clickTimer, setClickTimer] = useState(null);
  // P7-T5: opening/closing dialogs
  const [openingDismissed, setOpeningDismissed] = useState(false);
  const [closingOpen, setClosingOpen] = useState(false);

  useEffect(() => {
    setLoading(true);
    getPosContext()
      .then((res) => setContext(res.message || res))
      .catch((e) => setError(parseErrorMessage(e)));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="font-display text-2xl text-nds-cream">Loading NDS Restaurant…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="max-w-md text-center">
          <h1 className="font-display text-3xl mb-3">NDS Restaurant</h1>
          <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4 mb-4">
            <p className="text-red-300 mb-2 font-medium">Configuration error</p>
            <p className="text-red-200 text-sm whitespace-pre-wrap">{error}</p>
          </div>
          <button
            onClick={() => {
              setError(null);
              setLoading(true);
              getPosContext()
                .then((res) => setContext(res.message || res))
                .catch((e) => setError(parseErrorMessage(e)));
            }}
            className="px-4 py-2 rounded bg-nds-accent text-nds-green font-medium hover:opacity-90 mr-2"
          >
            Retry
          </button>
          <p className="text-nds-muted text-sm mt-4">Ensure POS Profile, Opening Entry, and Restaurant are configured.</p>
        </div>
      </div>
    );
  }

  const courses = context.courses || [];
  const lowStockThreshold = context.settings?.low_stock_threshold ?? 5;
  // P8-T1: aggregator price-list rates (Item Price) override the menu rate where they exist
  const aggRates = orderType === "Aggregator" && aggregator?.rates ? aggregator.rates : null;
  const pricedMenu = aggRates
    ? (context.menu_items || []).map((i) => {
        const variants = Array.isArray(i.variants)
          ? i.variants.map((v) => (v && typeof v === "object" && aggRates[v.item] != null ? { ...v, rate: aggRates[v.item] } : v))
          : i.variants;
        return aggRates[i.item] != null ? { ...i, rate: aggRates[i.item], variants } : { ...i, variants };
      })
    : context.menu_items || [];
  const items = pricedMenu.filter((i) => {
    if (i.grid_hidden) return false;
    if (courseFilter === "__specials__") {
      if (!i.special_dish) return false;
    } else if (courseFilter && i.course !== courseFilter) {
      return false;
    }
    return i.availability === null || i.availability === undefined || i.availability > 0;
  });
  const capabilities = context.capabilities || {};
  // Older servers don't send capabilities: keep the previous (everyone can bill) behaviour.
  const canBill = capabilities.can_bill === undefined ? true : !!capabilities.can_bill;
  const canRemoveItems = capabilities.can_remove_items === undefined ? true : !!capabilities.can_remove_items;
  const total = cartTotal();
  const payableTotal = invoiceGrandTotal != null ? invoiceGrandTotal : total;

  function handleItemClick(item) {
    const hasVariants = Array.isArray(item.variants) && item.variants.length > 0;
    if (hasVariants && item.base_sellable === 0) {
      // The base item can't be sold on its own: always pick a variant.
      setDialogItem(item);
      return;
    }
    if (clickTimer) {
      clearTimeout(clickTimer);
      setClickTimer(null);
      setDialogItem(item);
      return;
    }
    const timer = setTimeout(() => {
      setClickTimer(null);
      addToCart(item, 1);
    }, 220);
    setClickTimer(timer);
  }

  function handleDialogAdd(item, qty, notes, addons, parentItem) {
    addToCart(item, qty, notes, addons, parentItem);
  }

  async function placeOrder(generateKot = 1) {
    if (!cart.length) return null;
    try {
      const res = await createOrUpdateOrder({
        pos_profile: context.pos_profile,
        customer: customer?.name || undefined,
        items: JSON.stringify(cart.map(cartLinePayload)),
        table: selectedTable,
        order_type: orderType,
        invoice: invoice || undefined,
        comments,
        generate_kot: generateKot,
        expected_modified: expectedModified || undefined,
        aggregator: orderType === "Aggregator" ? aggregator?.customer : undefined,
        aggregator_order_id: orderType === "Aggregator" ? aggregatorOrderId || "" : undefined,
      });
      const data = res.message || res;
      applySavedOrder(data);
      // P5-T1: the order is saved even when the kitchen tickets fail
      if (data?.kot_error) showUserAlert(`Order saved, but KOT failed: ${data.kot_error}`, "red");
      (data?.kot_warnings || []).forEach((w) => showUserAlert(w, "yellow"));
      await refreshContext();
      return data;
    } catch (e) {
      const msg = parseErrorMessage(e);
      const reopenMatch = /open order\s+([^\s,]+),\s*reopen it/i.exec(msg);
      if (reopenMatch?.[1]) {
        try {
          const invRes = await getInvoice(reopenMatch[1]);
          const inv = invRes?.message || invRes;
          if (inv) {
            applySavedOrder({
              invoice: inv.name || reopenMatch[1],
              modified: inv.modified,
              grand_total: inv.grand_total,
              items: inv.items,
              sent_items: inv.sent_items || [],
            });
            usePOSStore.setState({
              comments: inv.custom_order_comments || "",
              orderType: inv.custom_nds_order_type || orderType,
              customer: inv.customer
                ? { name: inv.customer, customer_name: inv.customer_name || inv.customer }
                : customer,
              view: "menu",
            });
          }
        } catch (loadErr) {
          console.error("Failed to reopen table order:", loadErr);
        }
      }
      showUserAlert(msg);
      throw e;
    }
  }

  async function pay(mode, discountPercentage = 0, discountAmount = 0, overrideTotal = null) {
    try {
      let targetInvoice = invoice;
      let targetTotal = overrideTotal !== null ? overrideTotal : payableTotal;

      // Save unsent cart changes first so we never charge a stale invoice.
      if (cart.length > 0 && (!targetInvoice || cartDirty)) {
        const data = await placeOrder(1);
        targetInvoice = data.invoice;
        targetTotal = data.grand_total ?? targetTotal;
      }

      if (!targetInvoice) {
        showUserAlert("No active invoice found for payment.");
        return;
      }

      const result = await submitPayment(
        targetInvoice,
        [{ mode_of_payment: mode, amount: targetTotal }],
        discountPercentage,
        discountAmount
      );

      const invoiceName = result.message?.invoice || result.invoice || targetInvoice;
      setLastInvoice(invoiceName);
      if (context.settings?.auto_print) {
        printBill(invoiceName, context.settings?.print_format || "NDS Receipt", { quiet: true });
      }
      clearCart();
      const refreshed = await getPosContext(context.pos_profile);
      setContext(refreshed.message || refreshed);
      setView("tables");
    } catch (e) {
      showUserAlert(parseErrorMessage(e));
    }
  }

  async function handlePlaceAndPay() {
    if (!cart.length) return;
    if (orderType === "Aggregator") return handleAggregatorSettle();

    try {
      const payload = {
        pos_profile: context.pos_profile,
        customer: customer?.name || undefined,
        items: JSON.stringify(cart.map(cartLinePayload)),
        comments,
      };

      const response = await settleTakeaway(payload);
      const data = response.message || response;

      if (data.invoice) {
        setInvoice(data.invoice);
        setLastInvoice(data.invoice);
      }

      if (data.settled) {
        if (context.settings?.auto_print) {
          printBill(data.invoice, context.settings?.print_format || "NDS Receipt", { quiet: true });
        }
        clearCart();

        showUserAlert("Order Placed and Paid Successfully", "green");
      } else {
        const errorMsg = data.error || "Payment failed, order saved as Draft";
        showUserAlert(errorMsg, "orange");
      }
    } catch (e) {
      showUserAlert(parseErrorMessage(e));
    }
  }

  // P8-T2: send the aggregator order to the kitchen, then settle it per the Branch settings
  async function handleAggregatorSettle() {
    if (!aggregator) {
      showUserAlert("Select an aggregator first");
      return;
    }
    let data;
    try {
      data = await placeOrder(1);
    } catch {
      return; /* alert already shown */
    }
    if (!data?.invoice) return;
    try {
      const res = await settleAggregator(data.invoice);
      const out = res.message || res;
      if (out.keep_unpaid) {
        setLastInvoice(null);
        showUserAlert(`Sent to kitchen · unpaid invoice ${out.sales_invoice} for ${aggregator.customer_name || aggregator.customer}`, "green");
      } else {
        setLastInvoice(out.invoice);
        if (context.settings?.auto_print) {
          printBill(out.invoice, context.settings?.print_format || "NDS Receipt", { quiet: true });
        }
        showUserAlert(`Settled with ${out.mode_of_payment}`, "green");
      }
      clearCart();
      await refreshContext();
    } catch (e) {
      showUserAlert(`Order ${data.invoice} saved as draft: ${parseErrorMessage(e)}`, "orange");
    }
  }

  const needsPrint =
    !!context.settings?.print_before_pay && orderType === "Dine In" && !!selectedTable && !invoicePrinted;

  async function handlePrintBill() {
    try {
      let targetInvoice = invoice;
      if (cart.length > 0 && (!targetInvoice || cartDirty)) {
        const data = await placeOrder(1);
        targetInvoice = data?.invoice;
      }
      if (!targetInvoice) {
        showUserAlert("Add items before printing the bill.");
        return;
      }
      const printed = await printBill(targetInvoice, context.settings?.print_format || "NDS Receipt");
      setInvoicePrinted(true);
      setLastInvoice(targetInvoice);
      if (printed?.printed) showUserAlert(`Bill sent to ${printed.printer}`, "green");
    } catch (e) {
      showUserAlert(parseErrorMessage(e));
    }
  }

  async function handleSend() {
    try {
      await placeOrder(1);
    } catch {
      /* alert already shown */
    }
  }

  return (
    <div className="h-screen w-full max-w-full flex flex-col overflow-hidden">
      <header className="shrink-0 flex flex-wrap items-center justify-between gap-2 px-4 py-2 border-b border-white/10 bg-black/20 backdrop-blur">
        <div>
          <h1 className="font-display text-2xl tracking-wide">NDS Restaurant</h1>
          <p className="text-xs text-nds-muted">
            {context.restaurant?.name} · {context.pos_profile}
            {!context.opening && <span className="text-amber-300"> · No opening entry</span>}
          </p>
        </div>
        <nav className="flex flex-wrap justify-end items-center gap-2">
          {context.settings?.qz_print ? <QzStatus host={context.settings?.qz_host} /> : null}
          {[
            ["tables", "Tables"],
            ["menu", "Menu"],
            ["cart", `Cart (${cart.length})`],
            ["orders", "Orders"],
          ].map(([k, label]) => (
            <button
              key={k}
              onClick={() => setView(k)}
              className={`px-3 py-1.5 text-sm rounded ${
                view === k ? "bg-nds-accent text-nds-green" : "bg-white/10 hover:bg-white/20"
              }`}
            >
              {label}
            </button>
          ))}
          <button onClick={() => setOrderType("Take Away")} className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20">
            Take Away
          </button>
          {(context.aggregators || []).map((a) => (
            <button
              key={a.customer}
              onClick={() => setAggregator(a)}
              data-testid={`aggregator-${a.customer}`}
              title={[a.price_list && `Price: ${a.price_list}`, a.without_tax ? "No tax" : "", a.keep_unpaid ? "Keep unpaid" : `Pay: ${a.mode_of_payment || "default"}`].filter(Boolean).join(" · ")}
              className={`px-3 py-1.5 text-sm rounded ${
                orderType === "Aggregator" && aggregator?.customer === a.customer
                  ? "bg-orange-500 text-white"
                  : "bg-orange-500/20 hover:bg-orange-500/30"
              }`}
            >
              {a.customer_name || a.customer}
            </button>
          ))}
          {canBill && (context.opening || (context.shift_kind === "Sub POS Closing" && context.profile_opening)) && (
            <button
              onClick={() => setClosingOpen(true)}
              data-testid="close-shift"
              className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20"
            >
              Close Shift
            </button>
          )}
          {canBill && !context.opening && !context.profile_opening && (
            <button
              onClick={() => setOpeningDismissed(false)}
              data-testid="open-shift"
              className="px-3 py-1.5 text-sm rounded bg-amber-500/20 hover:bg-amber-500/30"
            >
              Open Shift
            </button>
          )}
          <button
            onClick={() => lastInvoice && printBill(lastInvoice, context.settings?.print_format || "NDS Receipt", { quiet: true })}
            disabled={!lastInvoice}
            className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Print Last Receipt
          </button>
        </nav>
      </header>

      <main className="flex-1 min-h-0 min-w-0 flex overflow-hidden">
        {view === "tables" && <FloorPlan />}

        {view === "menu" && (
          <>
            <MenuView
              courses={courses}
              items={items}
              courseFilter={courseFilter}
              setCourseFilter={setCourseFilter}
              onItemClick={handleItemClick}
              context={context}
              orderType={orderType}
              selectedTable={selectedTable}
              lowStockThreshold={lowStockThreshold}
            />
            <CartPanel
              cart={cart}
              total={payableTotal}
              comments={comments}
              setComments={setComments}
              updateQty={updateQty}
              onSend={handleSend}
              onPay={() => setView("pay")}
              orderType={orderType}
              onPlaceAndPay={handlePlaceAndPay}
              canBill={canBill}
              sentItems={sentItems}
              canRemoveItems={canRemoveItems}
              aggregator={orderType === "Aggregator" ? aggregator : null}
              aggregatorOrderId={aggregatorOrderId}
              setAggregatorOrderId={setAggregatorOrderId}
            />
          </>
        )}

        {view === "cart" && (
          <div className="flex-1 min-w-0 p-5 flex justify-center overflow-auto">
            <div className="w-full max-w-lg">
              <CartPanel
                cart={cart}
                total={payableTotal}
                comments={comments}
                setComments={setComments}
                updateQty={updateQty}
                onSend={handleSend}
                onPay={() => setView("pay")}
                full
                orderType={orderType}
                onPlaceAndPay={handlePlaceAndPay}
                canBill={canBill}
                sentItems={sentItems}
                canRemoveItems={canRemoveItems}
                aggregator={orderType === "Aggregator" ? aggregator : null}
                aggregatorOrderId={aggregatorOrderId}
                setAggregatorOrderId={setAggregatorOrderId}
              />
            </div>
          </div>
        )}

        {view === "pay" && !canBill && (
          <div className="flex-1 flex items-center justify-center p-6 text-nds-muted">Not permitted to bill</div>
        )}

        {view === "pay" && canBill && (
          <PayView
            total={payableTotal}
            payments={context.payments}
            pay={pay}
            setView={setView}
            context={context}
            needsPrint={needsPrint}
            onPrintBill={handlePrintBill}
          />
        )}

        {view === "orders" && <OrdersView />}
      </main>

      {canBill && !context.opening && !context.profile_opening && !openingDismissed && context.capabilities && (
        <OpeningDialog
          context={context}
          onOpened={() => refreshContext()}
          onLater={() => setOpeningDismissed(true)}
        />
      )}
      {closingOpen && (
        <CloseShiftDialog
          context={context}
          onClose={() => setClosingOpen(false)}
          onClosed={() => {
            setClosingOpen(false);
            setOpeningDismissed(true);
            refreshContext();
          }}
        />
      )}

      {dialogItem && (
        <ProductDialog item={dialogItem} context={context} onAdd={handleDialogAdd} onClose={() => setDialogItem(null)} />
      )}
    </div>
  );
}
