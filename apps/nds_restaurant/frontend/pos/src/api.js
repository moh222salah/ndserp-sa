import { FrappeApp } from "frappe-js-sdk";

const getSiteName = () => {
  if (window.frappe?.boot?.sitename) return window.frappe.boot.sitename;
  return window.location.hostname;
};

export const frappe = new FrappeApp(window.location.origin, {
  useToken: false,
  siteName: getSiteName(),
});

export const call = frappe.call();
export const db = frappe.db();

export async function getPosContext(posProfile) {
  return call.get("nds_restaurant.api.pos.get_pos_context", {
    pos_profile: posProfile || undefined,
  });
}

export async function createOrUpdateOrder(payload) {
  return call.post("nds_restaurant.api.pos.create_or_update_order", payload);
}

export async function submitPayment(invoice, payments, discountPercentage = 0, discountAmount = 0) {
  return call.post("nds_restaurant.api.pos.submit_payment", {
    invoice,
    payments: JSON.stringify(payments),
    discount_percentage: discountPercentage,
    discount_amount: discountAmount,
  });
}

export async function getOrders(posProfile, status, filters = {}) {
  const params = { pos_profile: posProfile, status };
  if (filters.table) params.table = filters.table;
  if (filters.captain) params.captain = filters.captain;
  if (filters.search) params.search = filters.search;
  if (filters.aggregator) params.aggregator = filters.aggregator;
  if (filters.limit) params.limit = filters.limit;
  return call.get("nds_restaurant.api.pos.get_orders", params);
}

export async function cancelOrder(invoice, reason = "") {
  return call.post("nds_restaurant.api.pos.cancel_order", { invoice, reason });
}

export function printInvoice(name, format) {
  const url = `/printview?doctype=POS%20Invoice&name=${encodeURIComponent(name)}&format=${encodeURIComponent(format)}&no_letterhead=1&trigger_print=1`;
  openPrintUrl(url);
}

export function printBillOnServer(invoice) {
  return call.post("nds_restaurant.api.printing.print_bill", { invoice });
}

export function markKotPickedUp(kotName) {
  return call.post("nds_restaurant.api.kot.mark_picked_up", { kot_name: kotName });
}

export function reprintKot(kotName) {
  return call.post("nds_restaurant.api.printing.reprint_kot", { kot_name: kotName });
}

// Open a /printview URL in a hidden iframe so the browser print dialog shows.
export function openPrintUrl(url) {
  const iframe = document.createElement("iframe");
  iframe.style.position = "fixed";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "none";
  iframe.src = url;
  document.body.appendChild(iframe);
  setTimeout(() => {
    if (iframe.parentNode) {
      iframe.parentNode.removeChild(iframe);
    }
  }, 60000);
}

export function markInvoicePrinted(invoice) {
  return call.post("nds_restaurant.api.pos.mark_invoice_printed", { invoice });
}

export function getInvoice(invoice) {
  return call.get("nds_restaurant.api.pos.get_invoice", { invoice });
}

export async function settleTakeaway(args) {
  const response = await fetch("/api/method/nds_restaurant.api.pos.settle_takeaway", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Frappe-CSRF-Token": window.csrf_token || "",
    },
    body: JSON.stringify(args),
  });

  return await response.json();
}

export async function searchCustomers(query) {
  const response = await fetch(`/api/method/nds_restaurant.api.pos.search_customers?query=${encodeURIComponent(query)}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "X-Frappe-CSRF-Token": window.csrf_token || "",
    },
  });
  return await response.json();
}

export async function createCustomer(customer_name, mobile_number) {
  const response = await fetch("/api/method/nds_restaurant.api.pos.create_customer", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Frappe-CSRF-Token": window.csrf_token || "",
    },
    body: JSON.stringify({ customer_name, mobile_number }),
  });
  return await response.json();
}

export async function changeOrderType(invoice, orderType, table = null) {
  const response = await fetch("/api/method/nds_restaurant.api.pos.change_order_type", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Frappe-CSRF-Token": window.csrf_token || "",
    },
    body: JSON.stringify({ invoice, order_type: orderType, table }),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.exc ? "Server Error" : errorData._server_messages || "Failed to change order type");
  }
  return await response.json();
}

// P4-T4: captain transfer, table move and merge
export function getTransferOptions(invoice) {
  return call.get("nds_restaurant.api.pos.get_transfer_options", { invoice });
}

export function captainTransfer(invoice, { toUser = null, toTable = null, expectedModified = null } = {}) {
  const payload = { invoice };
  if (toUser) payload.to_user = toUser;
  if (toTable) payload.to_table = toTable;
  if (expectedModified) payload.expected_modified = expectedModified;
  return call.post("nds_restaurant.api.pos.captain_transfer", payload);
}

export function mergeOrders(sourceInvoice, targetInvoice) {
  return call.post("nds_restaurant.api.pos.merge_orders", {
    source_invoice: sourceInvoice,
    target_invoice: targetInvoice,
  });
}

// P7-T5: shifts from the POS
export async function createOpening(posProfile, balanceDetails) {
  return call.post("nds_restaurant.api.shift.create_opening", {
    pos_profile: posProfile,
    balance_details: JSON.stringify(balanceDetails || []),
  });
}

export async function getClosingPreview(posProfile) {
  return call.get("nds_restaurant.api.shift.get_closing_preview", { pos_profile: posProfile });
}

export async function closeShift(posProfile, closingAmounts) {
  return call.post("nds_restaurant.api.shift.close_shift", {
    pos_profile: posProfile,
    closing_amounts: JSON.stringify(closingAmounts || {}),
  });
}

// P8-T2: settle a draft aggregator order (paid, or Keep Unpaid -> receivable Sales Invoice)
export async function settleAggregator(invoice, modeOfPayment) {
  return call.post("nds_restaurant.api.aggregators.settle_aggregator", {
    invoice,
    mode_of_payment: modeOfPayment || undefined,
  });
}
