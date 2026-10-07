import { create } from "zustand";
import { getInvoice } from "./api";

export const usePOSStore = create((set, get) => ({
  context: null,
  loading: true,
  error: null,
  view: "tables", // tables | menu | cart | orders | pay
  selectedTable: null,
  orderType: "Dine In",
  courseFilter: null,
  cart: [],
  invoice: null,
  customer: null,
  comments: "",
  lastInvoice: null,

  setContext: (context) => set({ context, loading: false }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
  setView: (view) => set({ view }),


 fetchDynamicMenu: async (room = null, orderType = null) => {
    const { context } = get();
    if (!context?.pos_profile) return;
    try {
      const url = `/api/method/nds_restaurant.api.pos.get_menu?pos_profile=${encodeURIComponent(context.pos_profile)}&room=${encodeURIComponent(room || '')}&order_type=${encodeURIComponent(orderType || '')}`;
      const res = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'X-Frappe-CSRF-Token': window.frappe?.csrf_token || ''
        }
      });
      const data = await res.json();
      const result = data.message;
      if (result && result.items) {
        set({
          context: {
            ...context,
            menu_items: result.items,
            price_list: result.price_list
          }
        });
      }
    } catch (e) {
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
            cart: (inv.items || []).map((i, idx) => ({
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
            })),
            comments: inv.custom_order_comments || "",
            orderType: inv.custom_nds_order_type || "Dine In",
            customer: inv.customer ? { name: inv.customer, customer_name: inv.customer_name || inv.customer } : null,
            view: "menu",
          });
        } else {
          set({ invoice: null, cart: [], comments: "", orderType: "Dine In", view: "menu" });
        }
      } catch (e) {
        console.error("Failed to load invoice:", e);
        set({ invoice: null, cart: [], comments: "", orderType: "Dine In", view: "menu" });
      }
    } else {
      set({ invoice: null, cart: [], comments: "", orderType: "Dine In", view: "menu" });
    }
  },


  setOrderType: (newOrderType) => {
    const selected = newOrderType === "Take Away" ? null : get().selectedTable;
    set({
      orderType: newOrderType,
      selectedTable: selected,
      view: "menu",
    });

    const context = get().context;
    const table = selected ? context?.tables?.find((t) => t.name === selected) : null;
    const room = table ? table.restaurant_room : null;
    
    get().fetchDynamicMenu(room, newOrderType);
  },
  // ----------------------------------------------------------

  setCourseFilter: (courseFilter) => set({ courseFilter }),
  setCustomer: (customer) => set({ customer }),
  setComments: (comments) => set({ comments }),
  setInvoice: (invoice) => set({ invoice }),
  setLastInvoice: (lastInvoice) => set({ lastInvoice }),

  // P3-T6: addToCart with support for notes, add-ons, and line grouping
  addToCart: (item, qty = 1, notes = "", addons = new Set(), parentItem = null) => {
    const cart = [...get().cart];
    
    // Generate unique line_id for this cart line
    const lineId = `line-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // For simple add (no notes, no addons), try to merge with existing line
    if (!notes && addons.size === 0 && !parentItem) {
      const idx = cart.findIndex((c) => c.item === item.item && !c.notes && !c.is_addon);
      if (idx >= 0) {
        cart[idx] = { ...cart[idx], qty: cart[idx].qty + qty };
        set({ cart, view: "menu" });
        return;
      }
    }
    
    // Add parent item
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
    
    // Add add-ons as separate lines
    if (addons.size > 0) {
      // Get the current addons list from item
      const addonsList = Array.isArray(item.addons) ? item.addons : [];
      addons.forEach((addonItem) => {
        const addon = addonsList.find((a) => 
          typeof a === "object" ? a.item === addonItem : a === addonItem
        );
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
    
    set({ cart, view: "menu" });
  },

  // P3-T6: updateQty with add-on synchronization
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
        } else if (c.addon_group_id === resolvedLineId) {
          return { ...c, qty };
        }
        return c;
      });
    }
    set({ cart });
  },

  clearCart: () =>
    set({
      cart: [],
      invoice: null,
      customer: null,
      comments: "",
      selectedTable: null,
      view: "tables",
    }),

  cartTotal: () => get().cart.reduce((s, c) => s + c.rate * c.qty, 0),
}));