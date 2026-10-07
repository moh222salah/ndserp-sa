/**
 * P6-T5: optional QZ Tray printing. Everything here is best effort: when QZ Tray is not
 * installed or not running, callers fall back to network/browser printing.
 * The signing key never reaches the browser; the server signs QZ requests (SHA512).
 */
import qz from "qz-tray";
import { call } from "../api";

const listeners = new Set();
let online = false;
let securityReady = false;
let connecting = null;

function setOnline(value) {
  online = value;
  listeners.forEach((fn) => {
    try {
      fn(value);
    } catch {}
  });
}

export function qzOnline() {
  return online;
}

export function onQzStatus(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function setupSecurity() {
  if (securityReady) return;
  securityReady = true;
  qz.security.setCertificatePromise((resolve) => {
    call
      .get("nds_restaurant.api.printing.qz_certificate")
      .then((r) => resolve((r && r.message) || null))
      .catch(() => resolve(null));
  });
  qz.security.setSignatureAlgorithm("SHA512");
  qz.security.setSignaturePromise((toSign) => (resolve) => {
    call
      .post("nds_restaurant.api.printing.qz_sign", { message: toSign })
      .then((r) => resolve((r && r.message) || null))
      .catch(() => resolve(null));
  });
}

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out`)), ms)),
  ]);
}

export async function qzConnect(host) {
  setupSecurity();
  if (qz.websocket.isActive()) {
    setOnline(true);
    return true;
  }
  if (!connecting) {
    connecting = withTimeout(
      qz.websocket.connect({
        host: host || "localhost",
        usingSecure: window.location.protocol === "https:",
        retries: 0,
        delay: 0,
      }),
      6000,
      "QZ Tray connection"
    )
      .then(() => {
        qz.websocket.setClosedCallbacks(() => setOnline(false));
        setOnline(true);
        return true;
      })
      .catch((e) => {
        setOnline(false);
        throw e;
      })
      .finally(() => {
        connecting = null;
      });
  }
  return connecting;
}

export async function qzPrintHtml(html, { host, printer } = {}) {
  await qzConnect(host);
  const target = printer || (await qz.printers.getDefault());
  if (!target) throw new Error("QZ Tray has no default printer");
  const config = qz.configs.create(target, { scaleContent: true });
  await withTimeout(
    qz.print(config, [{ type: "pixel", format: "html", flavor: "plain", data: html }]),
    20000,
    "QZ print"
  );
  return target;
}
