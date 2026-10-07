import { useState } from "react";
import { createOpening } from "../api";
import { parseErrorMessage, showUserAlert } from "../lib/errors";

// P7-T5: shown to a cashier/manager without an open POS shift. "Later" hides it for this page load
// (in multi-cashier mode captains and cashiers can still work on the main cashier's shift).
export default function OpeningDialog({ context, onOpened, onLater }) {
  const modes = (context.payments || []).map((p) => p.mode_of_payment);
  const [amounts, setAmounts] = useState(() => Object.fromEntries(modes.map((m) => [m, ""])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const rows = modes.map((m) => ({ mode_of_payment: m, opening_amount: Number(amounts[m] || 0) }));
      const res = await createOpening(context.pos_profile, rows);
      const opened = res.message || res;
      showUserAlert(`Shift opened (${opened.name})`, "green");
      onOpened && onOpened(opened);
    } catch (err) {
      setError(parseErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" data-testid="opening-dialog">
      <form onSubmit={submit} className="w-full max-w-md rounded-xl bg-nds-green border border-white/10 p-5 shadow-xl">
        <h2 className="font-display text-2xl mb-1">Open POS shift</h2>
        <p className="text-sm text-nds-muted mb-4">{context.pos_profile} · opening amounts per mode of payment</p>
        <div className="space-y-2 mb-4">
          {modes.map((m) => (
            <label key={m} className="flex items-center justify-between gap-3">
              <span className="text-sm">{m}</span>
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                data-testid={`opening-amount-${m}`}
                value={amounts[m]}
                onChange={(e) => setAmounts({ ...amounts, [m]: e.target.value })}
                className="w-36 px-2 py-1 rounded bg-black/30 border border-white/10 text-right"
                placeholder="0.00"
              />
            </label>
          ))}
        </div>
        {error && <p className="text-sm text-red-300 mb-3 whitespace-pre-wrap" data-testid="opening-error">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onLater} className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20">
            Later
          </button>
          <button
            type="submit"
            disabled={busy}
            data-testid="opening-submit"
            className="px-4 py-1.5 text-sm rounded bg-nds-accent text-nds-green font-medium disabled:opacity-50"
          >
            {busy ? "Opening…" : "Open shift"}
          </button>
        </div>
      </form>
    </div>
  );
}
