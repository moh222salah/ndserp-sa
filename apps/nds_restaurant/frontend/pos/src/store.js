import { create } from "zustand";
import { getInvoice, getPosContext } from "./api";
import { showUserAlert } from "./lib/errors";

export const UNASSIGNED_ROOM = "Unassigned";

function mapInvoiceItemsToCart(items) {
  return (items || []).map((i, idx) => ({
    line_id: i.addon_group_id
      ? `addon-reload-${idx}-${i.item_code || i.item}`
      : `line-reload-${idx}-${i.item_code || i.item}`,
    item: i.item_code || i.item,
    item_name: i.item_name,
    rate: i.rate,
    qty: i.qty,
    image: i.image,
    notes: i.notes || i.custom_nds_notes || "",
    is_addon: !!(i.is_addon || i.custom_is_addon),
    addon_group_id: i.addon_group_id || i.custom_addon_group_id || null,
    course: i.course || i.custom_nds_course || null,
  }));
}

function aggregatorRow(context, customer) {
  const rows = context?.aggregators || [];
  return rows.find((r) => r.customer === customer) || { customer, customer_name: customer, rates: {} };
}

export const usePOSStore = create((set, get) => ({
  context: null,
  loading: true,
  error: null,
  view: "tables",
  selectedTable: null,
  orderType: "Dine In",
  courseFilter: null,
  cart: [],
  invoice: null,
  expectedModified: null,
  invoiceGrandTotal: null,
  invoicePrinted: false,
  cartDirty: false,
  sentItems: [],
  customer: null,
  // P8-T1: the selected aggregator (Branch row) and the platform order id
  aggregator: null,
  aggregatorOrderId: "",
  comments: "",
  lastInvoice: null,
  menuFetchRequestId: 0,

  setContext: (context) => set({ context, loading: false }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
  setView: (view) => set({ view }),

  refreshContext: async () => {
    const { context } = get();
    if (!context?.pos_profile) return;
    try {
      const res = await getPosContext(context.pos_profile);
      set({ context: res.message || res });
    } catch (e) {
      console.error("Failed to refresh POS context:", e);
    }
  },

  applySavedOrder: (data) => {
    if (!data) return;
    const cart = data.items ? mapInvoiceItemsToCart(data.items) : get().cart;
    set({
      invoice: data.invoice,
      expectedModified: data.modified || null,
      invoiceGrandTotal: data.grand_total != null ? data.grand_total : get().invoiceGrandTotal,
      invoicePrinted: data.invoice_printed != null ? !!data.invoice_printed : get().invoicePrinted,
      sentItems: Array.isArray(data.sent_items) ? data.sent_items : get().sentItems,
      cartDirty: false,
      cart,
    });
  },

  setInvoicePrinted: (invoicePrinted) => set({ invoicePrinted: !!invoicePrinted }),

  // Load a saved order (from get_invoice) into the cart, e.g. from the Orders page.
  openInvoice: (inv, view = "menu") => {
    if (!inv) return;
    const table = inv.table || inv.custom_nds_table || null;
    const orderType = inv.order_type || inv.custom_nds_order_type || (table ? "Dine In" : "Take Away");
    set({
      invoice: inv.name || inv.invoice,
      expectedModified: inv.modified || null,
      invoiceGrandTotal: inv.grand_total ?? null,
      invoicePrinted: !!inv.invoice_printed,
      sentItems: inv.sent_items || [],
      cartDirty: false,
      cart: mapInvoiceItemsToCart(inv.items),
      comments: inv.custom_order_comments || "",
      orderType,
      selectedTable: orderType === "Take Away" || orderType === "Aggregator" ? null : table,
      customer: inv.customer ? { name: inv.customer, customer_name: inv.customer_name || inv.customer } : null,
      aggregator: inv.aggregator ? aggregatorRow(get().context, inv.aggregator) : null,
      aggregatorOrderId: inv.aggregator_order_id || "",
      view,
    });
    const context = get().context;
    const tableRow = table ? context?.tables?.find((t) => t.name === table) : null;
    get().fetchDynamicMenu(tableRow ? tableRow.restaurant_room : inv.room || null, orderType);
  },

  fetchDynamicMenu: async (room = null, orderType = null) => {
    const { context, menuFetchRequestId } = get();
    if (!context?.pos_profile) return;
    const requestId = menuFetchRequestId + 1;
    set({ menuFetchRequestId: requestId });
    try {
      const url = `/api/method/nds_restaurant.api.pos.get_menu?pos_profile=${encodeURIComponent(context.pos_profile)}&room=${encodeURIComponent(room || "")}&order_type=${encodeURIComponent(orderType || "")}`;
      const res = await fetch(url, {
        headers: {
          Accept: "application/json",
          "X-Frappe-CSRF-Token": window.csrf_token || "",
        },
      });
      const data = await res.json();
      if (!res.ok) {
        const err =
          data._server_messages ||
          data.exc ||
          data.message?.exc ||
          "Failed to load menu";
        showUserAlert(err);
        return;
      }
      if (get().menuFetchRequestId !== requestId) return;
      const result = data.message;
      if (result && result.items) {
        set({
          context: {
            ...get().context,
            menu_items: result.items,
            price_list: result.price_list,
            menu: result.menu,
          },
        });
      }
    } catch (e) {
      if (get().menuFetchRequestId === requestId) {
        showUserAlert(e.message || "Failed to fetch menu");
      }
      console.error("Failed to fetch dynamic menu:", e);
    }
  },

  setSelectedTable: async (tableName) => {
    set({ selectedTable: tableName });
    const { context, orderType, fetchDynamicMenu } = get();
    const table = context?.tables?.find((t) => t.name === tableName);

    const room = table ? table.restaurant_room : null;
    fetchDynamicMenu(room, orderType);

    if (table && table.occupied && table.current_invoice) {
      try {
        const res = await getInvoice(table.current_invoice);
        const inv = res?.message || res;

        if (inv && (inv.name || inv.items)) {
          set({
            invoice: inv.name || table.current_invoice,
            expectedModified: inv.modified || null,
            invoiceGrandTotal: inv.grand_total ?? null,
            invoicePrinted: !!inv.invoice_printed,
            sentItems: inv.sent_items || [],
            cartDirty: false,
            cart: mapInvoiceItemsToCart(inv.items),
            comments: inv.custom_order_comments || "",
            orderType: inv.custom_nds_order_type || "Dine In",
            customer: inv.customer ? { name: inv.customer, customer_name: inv.customer_name || inv.customer } : null,
            view: "menu",
          });
        } else {
          set({
            invoice: null,
            expectedModified: null,
            invoiceGrandTotal: null,
            invoicePrinted: false,
            sentItems: [],
            cartDirty: false,
            cart: [],
            comments: "",
            orderType: "Dine In",
            view: "menu",
          });
        }
      } catch (e) {
        console.error("Failed to load invoice:", e);
        showUserAlert(e.message || "Failed to load table order");
        set({
          invoice: null,
          expectedModified: null,
          invoiceGrandTotal: null,
          invoicePrinted: false,
          sentItems: [],
          cartDirty: false,
          cart: [],
          comments: "",
          orderType: "Dine In",
          view: "menu",
        });
      }
    } else {
      set({
        invoice: null,
        expectedModified: null,
        invoiceGrandTotal: null,
        invoicePrinted: false,
        sentItems: [],
        cartDirty: false,
        cart: [],
        comments: "",
        orderType: "Dine In",
        view: "menu",
      });
    }
  },

  setOrderType: (newOrderType) => {
    const selected = newOrderType === "Take Away" || newOrderType === "Aggregator" ? null : get().selectedTable;
    const leavingAggregator = newOrderType !== "Aggregator" && get().aggregator;
    set({
      orderType: newOrderType,
      selectedTable: selected,
      view: "menu",
      ...(newOrderType !== "Aggregator" ? { aggregator: null, aggregatorOrderId: "" } : {}),
      ...(leavingAggregator ? { customer: null } : {}),
    });

    const context = get().context;
    const table = selected ? context?.tables?.find((t) => t.name === selected) : null;
    const room = table ? table.restaurant_room : null;

    get().fetchDynamicMenu(room, newOrderType);
  },

  // P8-T1: an aggregator button sets the order type, the aggregator and its (locked) customer
  setAggregator: (row) => {
    if (!row) return;
    set({
      orderType: "Aggregator",
      aggregator: row,
      customer: { name: row.customer, customer_name: row.customer_name || row.customer },
      selectedTable: null,
      view: "menu",
    });
    get().fetchDynamicMenu(null, "Aggregator");
  },
  setAggregatorOrderId: (aggregatorOrderId) => set({ aggregatorOrderId }),

  setCourseFilter: (courseFilter) => set({ courseFilter }),
  setCustomer: (customer) => set({ customer }),
  setComments: (comments) => set({ comments }),
  setInvoice: (invoice) => set({ invoice }),
  setLastInvoice: (lastInvoice) => set({ lastInvoice }),

  addToCart: (item, qty = 1, notes = "", addons = new Set(), parentItem = null) => {
    const cart = [...get().cart];

    const lineId = `line-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    if (!notes && addons.size === 0 && !parentItem) {
      const idx = cart.findIndex((c) => c.item === item.item && !c.notes && !c.is_addon);
      if (idx >= 0) {
        cart[idx] = { ...cart[idx], qty: cart[idx].qty + qty };
        set({ cart, cartDirty: true, view: "menu" });
        return;
      }
    }

    const parentLine = {
      line_id: lineId,
      item: item.item,
      item_name: item.item_name,
      rate: item.rate,
      qty,
      image: item.image,
      notes: notes || "",
      is_addon: false,
      addon_group_id: null,
      course: item.course || null,
    };
    cart.push(parentLine);

    if (addons.size > 0) {
      const addonsList = Array.isArray(item.addons) ? item.addons : [];
      addons.forEach((addonItem) => {
        const addon = addonsList.find((a) => (typeof a === "object" ? a.item === addonItem : a === addonItem));
        if (addon) {
          const addonName = typeof addon === "object" ? addon.item_name : addonItem;
          const addonRate = typeof addon === "object" ? addon.rate : 0;
          cart.push({
            line_id: `addon-${lineId}-${addonItem}`,
            item: addonItem,
            item_name: addonName,
            rate: addonRate,
            qty,
            is_addon: true,
            addon_group_id: lineId,
            notes: "",
            course: null,
          });
        }
      });
    }

    set({ cart, cartDirty: true, view: "menu" });
  },

  updateQty: (lineId, qty) => {
    let cart = [...get().cart];
    const line = cart.find((c) => c.line_id === lineId || (!c.line_id && c.item === lineId));

    if (!line) return;
    const resolvedLineId = line.line_id;

    if (qty <= 0) {
      cart = cart.filter((c) => c.line_id !== resolvedLineId && c.addon_group_id !== resolvedLineId);
    } else {
      cart = cart.map((c) => {
        if (c.line_id === resolvedLineId) {
          return { ...c, qty };
        }
        if (c.addon_group_id === resolvedLineId) {
          return { ...c, qty };
        }
        return c;
      });
    }
    set({ cart, cartDirty: true });
  },

  clearCart: () =>
    set({
      cart: [],
      invoice: null,
      expectedModified: null,
      invoiceGrandTotal: null,
      invoicePrinted: false,
      sentItems: [],
      cartDirty: false,
      customer: null,
      aggregator: null,
      aggregatorOrderId: "",
      orderType: get().orderType === "Aggregator" ? "Dine In" : get().orderType,
      comments: "",
      selectedTable: null,
      view: "tables",
    }),

  cartTotal: () => get().cart.reduce((s, c) => s + c.rate * c.qty, 0),
}));
