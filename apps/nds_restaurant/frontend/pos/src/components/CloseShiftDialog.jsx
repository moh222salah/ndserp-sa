import { useEffect, useState } from "react";
import { closeShift, getClosingPreview } from "../api";
import { parseErrorMessage, showUserAlert } from "../lib/errors";

function money(v) {
  return Number(v || 0).toFixed(2);
}

// P7-T5: expected amounts per mode of payment, counted amounts, then a POS Closing Entry
// (or a Sub POS Closing for a sub-cashier in multi-cashier mode).
export default function CloseShiftDialog({ context, onClose, onClosed }) {
  const [preview, setPreview] = useState(null);
  const [counted, setCounted] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getClosingPreview(context.pos_profile)
      .then((res) => {
        const p = res.message || res;
        setPreview(p);
        setCounted(Object.fromEntries((p.payments || []).map((r) => [r.mode_of_payment, String(r.expected_amount ?? 0)])));
      })
      .catch((e) => setError(parseErrorMessage(e)));
  }, [context.pos_profile]);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const amounts = Object.fromEntries(Object.entries(counted).map(([m, v]) => [m, Number(v || 0)]));
      const res = await closeShift(context.pos_profile, amounts);
      const done = res.message || res;
      showUserAlert(`${done.doctype} ${done.name} submitted`, "green");
      onClosed && onClosed(done);
    } catch (e) {
      setError(parseErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const drafts = preview?.drafts || [];
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" data-testid="close-shift-dialog">
      <div className="w-full max-w-lg rounded-xl bg-nds-green border border-white/10 p-5 shadow-xl">
        <h2 className="font-display text-2xl mb-1">Close shift</h2>
        {preview && (
          <p className="text-sm text-nds-muted mb-3">
            {preview.opening} · {preview.invoice_count} paid orders · {money(preview.grand_total)} ·{" "}
            {preview.kind === "Sub POS Closing" ? "Sub POS Closing" : "POS Closing Entry"}
          </p>
        )}
        {!preview && !error && <p className="text-sm text-nds-muted mb-3">Loading…</p>}
        {drafts.length > 0 && (
          <p className="text-sm text-amber-300 mb-3" data-testid="close-drafts">
            Submit/Delete Draft Invoices: {drafts.join(", ")}
          </p>
        )}
        {preview && (
          <table className="w-full text-sm mb-4">
            <thead className="text-nds-muted">
              <tr>
                <th className="text-left font-normal py-1">Mode</th>
                <th className="text-right font-normal">Opening</th>
                <th className="text-right font-normal">Expected</th>
                <th className="text-right font-normal">Counted</th>
                <th className="text-right font-normal">Diff</th>
              </tr>
            </thead>
            <tbody>
              {(preview.payments || []).map((r) => {
                const diff = Number(counted[r.mode_of_payment] || 0) - Number(r.expected_amount || 0);
                return (
                  <tr key={r.mode_of_payment} className="border-t border-white/10" data-testid={`close-row-${r.mode_of_payment}`}>
                    <td className="py-1">{r.mode_of_payment}</td>
                    <td className="text-right">{money(r.opening_amount)}</td>
                    <td className="text-right" data-testid="close-expected">{money(r.expected_amount)}</td>
                    <td className="text-right">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        inputMode="decimal"
                        value={counted[r.mode_of_payment] ?? ""}
                        onChange={(e) => setCounted({ ...counted, [r.mode_of_payment]: e.target.value })}
                        className="w-28 px-2 py-0.5 rounded bg-black/30 border border-white/10 text-right"
                      />
                    </td>
                    <td className={`text-right ${diff < 0 ? "text-red-300" : diff > 0 ? "text-amber-300" : ""}`}>{money(diff)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {error && <p className="text-sm text-red-300 mb-3 whitespace-pre-wrap" data-testid="close-error">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy || !preview || drafts.length > 0}
            data-testid="close-submit"
            className="px-4 py-1.5 text-sm rounded bg-nds-accent text-nds-green font-medium disabled:opacity-50"
          >
            {busy ? "Closing…" : "Close shift"}
          </button>
        </div>
      </div>
    </div>
  );
}
