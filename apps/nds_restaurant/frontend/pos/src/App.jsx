import { useEffect, useState } from "react";
import { usePOSStore } from "./store";
import { parseErrorMessage } from "./lib/errors";
import { getPosContext, createOrUpdateOrder, submitPayment, printInvoice, settleTakeaway } from "./api";

import CartPanel from "./components/CartPanel";
import TablesView from "./views/TablesView";
import MenuView from "./views/MenuView";
import PayView from "./views/PayView";
import OrdersView from "./views/OrdersView";
import ProductDialog from "./components/ProductDialog";

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
    comments,
    lastInvoice,
    setContext,
    setLoading,
    setError,
    setView,
    setSelectedTable,
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
  } = usePOSStore();

  const [dialogItem, setDialogItem] = useState(null);
  const [clickTimer, setClickTimer] = useState(null);

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
            <p className="text-red-300 mb-2 font-medium">Error</p>
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
          <button onClick={() => setError(null)} className="px-4 py-2 rounded bg-white/10 hover:bg-white/20">
            Dismiss
          </button>
          <p className="text-nds-muted text-sm mt-4">Ensure POS Profile, Opening Entry, and Restaurant are configured.</p>
        </div>
      </div>
    );
  }

  const courses = context.courses || [];
  const lowStockThreshold = context.settings?.low_stock_threshold ?? 5;
  const items = (context.menu_items || []).filter((i) => {
    if (courseFilter === "__specials__") {
      if (!i.special_dish) return false;
    } else if (courseFilter && i.course !== courseFilter) {
      return false;
    }
    return i.availability === null || i.availability === undefined || i.availability > 0;
  });
  const tables = context.tables || [];
  const total = cartTotal();

  function handleItemClick(item) {
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
    if (!cart.length) return;
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
      });
      const data = res.message || res;
      setInvoice(data.invoice);
      return data;
    } catch (e) {
      setError(parseErrorMessage(e));
      throw e;
    }
  }

  async function pay(mode, discountPercentage = 0, discountAmount = 0, overrideTotal = null) {
    try {
      let targetInvoice = invoice;
      let targetTotal = overrideTotal !== null ? overrideTotal : total;

      if (cart.length > 0 && !targetInvoice) {
        const data = await placeOrder(1);
        targetInvoice = data.invoice;
      }

      if (!targetInvoice) {
        alert("No active invoice found for payment.");
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
        printInvoice(invoiceName, context.settings?.print_format || "NDS Receipt");
      }
      clearCart();
      const refreshed = await getPosContext(context.pos_profile);
      setContext(refreshed.message || refreshed);
      setView("tables");
    } catch (e) {
      setError(parseErrorMessage(e));
    }
  }

  async function handlePlaceAndPay() {
    if (!cart.length) return;

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
          printInvoice(data.invoice, context.settings?.print_format || "NDS Receipt");
        }
        clearCart();

        if (window.frappe) {
          window.frappe.show_alert({ message: "Order Placed and Paid Successfully", indicator: "green" });
        } else {
          alert("Order Placed and Paid Successfully");
        }
      } else {
        const errorMsg = data.error || "Payment failed, order saved as Draft";
        if (window.frappe) {
          window.frappe.show_alert({ message: errorMsg, indicator: "orange" });
        } else {
          alert(errorMsg);
        }
      }
    } catch (e) {
      setError(parseErrorMessage(e));
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-black/20 backdrop-blur">
        <div>
          <h1 className="font-display text-2xl tracking-wide">NDS Restaurant</h1>
          <p className="text-xs text-nds-muted">
            {context.restaurant?.name} · {context.pos_profile}
            {!context.opening && <span className="text-amber-300"> · No opening entry</span>}
          </p>
        </div>
        <nav className="flex gap-2">
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
          <button
            onClick={() => lastInvoice && printInvoice(lastInvoice, context.settings?.print_format || "NDS Receipt")}
            disabled={!lastInvoice}
            className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Print Last Receipt
          </button>
        </nav>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {view === "tables" && <TablesView tables={tables} setSelectedTable={setSelectedTable} />}

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
              total={total}
              comments={comments}
              setComments={setComments}
              updateQty={updateQty}
              onSend={() => placeOrder(1).then((d) => setInvoice(d.invoice)).catch(() => {})}
              onPay={() => setView("pay")}
              orderType={orderType}
              onPlaceAndPay={handlePlaceAndPay}
            />
          </>
        )}

        {view === "cart" && (
          <div className="flex-1 p-5 flex justify-center">
            <div className="w-full max-w-lg">
              <CartPanel
                cart={cart}
                total={total}
                comments={comments}
                setComments={setComments}
                updateQty={updateQty}
                onSend={() => placeOrder(1).then((d) => setInvoice(d.invoice)).catch(() => {})}
                onPay={() => setView("pay")}
                full
                orderType={orderType}
                onPlaceAndPay={handlePlaceAndPay}
              />
            </div>
          </div>
        )}

        {view === "pay" && <PayView total={total} payments={context.payments} pay={pay} setView={setView} context={context} />}

        {view === "orders" && <OrdersView />}
      </main>

      {dialogItem && (
        <ProductDialog item={dialogItem} context={context} onAdd={handleDialogAdd} onClose={() => setDialogItem(null)} />
      )}
    </div>
  );
}
