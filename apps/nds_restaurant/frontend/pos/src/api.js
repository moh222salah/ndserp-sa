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

export async function getOrders(posProfile, status) {
  return call.get("nds_restaurant.api.pos.get_orders", {
    pos_profile: posProfile,
    status,
  });
}

export function printInvoice(name, format) {
  const url = `/printview?doctype=POS%20Invoice&name=${encodeURIComponent(name)}&format=${encodeURIComponent(format)}&no_letterhead=1&trigger_print=1`;
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = 'none';
  iframe.src = url;
  document.body.appendChild(iframe);
  setTimeout(() => {
    if (iframe.parentNode) {
      iframe.parentNode.removeChild(iframe);
    }
  }, 60000);
}

export function markInvoicePrinted(invoice) {
  return frappe.call({
    method: "nds_restaurant.api.pos.mark_invoice_printed",
    args: { invoice }
  });
}

export function getInvoice(invoice) {
  return frappe.call({
    method: "nds_restaurant.api.pos.get_invoice",
    args: { invoice }
  });
}

export async function settleTakeaway(args) {
  const response = await fetch('/api/method/nds_restaurant.api.pos.settle_takeaway', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token || ''
    },
    body: JSON.stringify(args)
  });
  
  return await response.json();
}

export async function searchCustomers(query) {
  const response = await fetch(`/api/method/nds_restaurant.api.pos.search_customers?query=${encodeURIComponent(query)}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token || ''
    }
  });
  return await response.json();
}

export async function createCustomer(customer_name, mobile_number) {
  const response = await fetch('/api/method/nds_restaurant.api.pos.create_customer', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token || ''
    },
    body: JSON.stringify({ customer_name, mobile_number })
  });
  return await response.json();
}


export async function changeOrderType(invoice, orderType, table = null) {
  const response = await fetch('/api/method/nds_restaurant.api.pos.change_order_type', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token || ''
    },
    body: JSON.stringify({ invoice, order_type: orderType, table })
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.exc ? "Server Error" : errorData._server_messages || "Failed to change order type");
  }
  return await response.json();
}