import { call, markInvoicePrinted, openPrintUrl, printBillOnServer, printInvoice } from "../api";
import { usePOSStore } from "../store";
import { qzPrintHtml } from "./qz";

function qzSettings() {
  const settings = usePOSStore.getState().context?.settings || {};
  return settings.qz_print ? settings : null;
}

/**
 * P6-T5: print through QZ Tray on this till. Returns null when QZ is off for the profile
 * or not reachable, so the caller falls back to the network/browser path.
 */
async function printBillViaQz(invoice) {
  const settings = qzSettings();
  if (!settings) return null;
  try {
    const res = await call.get("nds_restaurant.api.printing.get_bill_html", { invoice });
    const html = res?.message || res;
    if (!html) return null;
    const printer = await qzPrintHtml(html, { host: settings.qz_host, printer: settings.qz_printer });
    let marked = {};
    try {
      const m = await markInvoicePrinted(invoice);
      marked = m?.message || m || {};
    } catch {}
    return { invoice, printed: true, method: "qz", printer, ...marked };
  } catch (e) {
    console.warn("QZ Tray print failed, falling back", e);
    return null;
  }
}

/**
 * P6-T2: print a bill. QZ Tray first when the profile enables it (P6-T5); otherwise the
 * server routes it to the room printer, then the POS Profile printer (and marks a draft
 * printed); without a network printer the browser prints it.
 *
 * quiet: never throw (auto-print after payment must not break the payment flow); on a
 * server error it falls back to browser printing.
 */
export async function printBill(invoice, fallbackFormat = "NDS Receipt", { quiet = false } = {}) {
  const viaQz = await printBillViaQz(invoice);
  if (viaQz) return viaQz;
  try {
    const res = await printBillOnServer(invoice);
    const data = res?.message || res || {};
    if (!data.printed) {
      if (data.print_url) openPrintUrl(data.print_url);
      else printInvoice(invoice, data.print_format || fallbackFormat);
    }
    return data;
  } catch (e) {
    if (!quiet) throw e;
    printInvoice(invoice, fallbackFormat);
    return { printed: false, method: "browser" };
  }
}
