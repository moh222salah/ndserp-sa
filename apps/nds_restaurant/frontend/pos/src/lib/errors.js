export function stripHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim();
}

export function parseErrorMessage(e) {
  let raw = "";
  if (e._server_messages) {
    try {
      const messages = JSON.parse(e._server_messages);
      raw = messages.map((m) => JSON.parse(m).message).join("; ");
    } catch {}
  }
  if (!raw) {
    raw = e.message || e.exc || String(e);
  }
  return stripHtml(raw);
}

export function showUserAlert(message, indicator = "red") {
  const text = stripHtml(message);
  if (window.frappe?.show_alert) {
    window.frappe.show_alert({ message: text, indicator });
  } else {
    window.alert(text);
  }
}