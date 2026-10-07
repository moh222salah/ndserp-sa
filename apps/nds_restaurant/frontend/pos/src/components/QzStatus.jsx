import { useEffect, useState } from "react";
import { onQzStatus, qzConnect, qzOnline } from "../lib/qz";

/** P6-T5: QZ Tray online/offline chip; only rendered when the profile enables QZ Print. */
export default function QzStatus({ host }) {
  const [online, setOnline] = useState(qzOnline());
  const [busy, setBusy] = useState(false);

  async function connect() {
    setBusy(true);
    try {
      await qzConnect(host);
    } catch {
      /* offline: printing falls back to network/browser */
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const off = onQzStatus(setOnline);
    connect();
    return off;
  }, [host]);

  return (
    <button
      onClick={connect}
      disabled={busy}
      title={online ? "QZ Tray connected" : "QZ Tray not reachable: bills use network/browser printing. Click to retry."}
      data-testid="qz-status"
      data-online={online ? "1" : "0"}
      className={`px-2 py-1 text-xs rounded border ${
        online ? "border-green-400 text-green-300" : "border-red-400 text-red-300"
      }`}
    >
      {busy ? "QZ…" : online ? "QZ online" : "QZ offline"}
    </button>
  );
}
