import React, { useEffect, useMemo, useState } from "react";
import { getTransferOptions, captainTransfer, mergeOrders } from "../api";
import { parseErrorMessage, showUserAlert } from "../lib/errors";

function shortUser(u) {
  return u ? String(u).split("@")[0] : "";
}

// P4-T4: hand an order to another captain, move it to a free table, or merge it into another order.
export default function TransferPanel({ invoice, expectedModified, onDone, onCancel }) {
  const [opts, setOpts] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toUser, setToUser] = useState("");
  const [toTable, setToTable] = useState("");
  const [mergeTarget, setMergeTarget] = useState("");

  useEffect(() => {
    let alive = true;
    getTransferOptions(invoice)
      .then((res) => {
        if (!alive) return;
        const data = res?.message || res;
        setOpts(data);
        setToUser("");
      })
      .catch((e) => alive && setError(parseErrorMessage(e)));
    return () => {
      alive = false;
    };
  }, [invoice]);

  const tablesByRoom = useMemo(() => {
    const groups = {};
    (opts?.tables || []).forEach((t) => {
      const room = t.room || "Unassigned";
      (groups[room] = groups[room] || []).push(t);
    });
    return groups;
  }, [opts]);

  async function run(fn, okMessage) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fn();
      const data = res?.message || res;
      showUserAlert(okMessage(data), "green");
      onDone && onDone(data);
    } catch (e) {
      showUserAlert(parseErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <div className="mb-3 rounded border border-red-500/40 bg-red-900/20 p-3 text-sm text-red-200" data-testid="transfer-panel">
        {error}
        <button onClick={onCancel} className="block mt-2 text-xs underline">Close</button>
      </div>
    );
  }
  if (!opts) {
    return <div className="mb-3 text-sm text-nds-muted" data-testid="transfer-panel">Loading transfer options…</div>;
  }

  const users = (opts.users || []).filter((u) => u.user !== opts.captain);
  const isDineIn = (opts.order_type || "Dine In") === "Dine In";

  return (
    <div className="mb-3 rounded-lg border border-white/15 bg-black/30 p-3 text-sm space-y-3" data-testid="transfer-panel">
      <div className="flex justify-between items-center">
        <p className="font-medium">Transfer {opts.invoice}</p>
        <button onClick={onCancel} className="text-nds-muted hover:text-white text-xs">Close</button>
      </div>

      <div>
        <label className="block text-xs text-nds-muted mb-1">Captain (now {shortUser(opts.captain)})</label>
        <div className="flex gap-2">
          <select
            value={toUser}
            onChange={(e) => setToUser(e.target.value)}
            className="flex-1 min-w-0 bg-black/40 border border-white/20 rounded px-2 py-1 text-xs"
            data-testid="transfer-user"
          >
            <option value="">Choose captain…</option>
            {users.map((u) => (
              <option key={u.user} value={u.user}>
                {u.full_name && u.full_name !== u.user ? `${u.full_name} (${shortUser(u.user)})` : u.user}
              </option>
            ))}
          </select>
          <button
            disabled={busy || !toUser}
            onClick={() =>
              run(
                () => captainTransfer(invoice, { toUser, expectedModified }),
                (d) => `Order handed to ${shortUser(d?.captain)}`
              )
            }
            className="px-2 py-1 rounded bg-white/15 hover:bg-white/25 text-xs disabled:opacity-40"
          >
            Hand over
          </button>
        </div>
      </div>

      {isDineIn && (
        <div>
          <label className="block text-xs text-nds-muted mb-1">Move to table (now {opts.table || "none"})</label>
          <div className="flex gap-2">
            <select
              value={toTable}
              onChange={(e) => setToTable(e.target.value)}
              className="flex-1 min-w-0 bg-black/40 border border-white/20 rounded px-2 py-1 text-xs"
              data-testid="transfer-table"
            >
              <option value="">Choose a free table…</option>
              {Object.entries(tablesByRoom).map(([room, tables]) => (
                <optgroup key={room} label={room}>
                  {tables.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name}
                      {t.seats ? ` · ${t.seats} seats` : ""}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <button
              disabled={busy || !toTable}
              onClick={() =>
                run(
                  () => captainTransfer(invoice, { toTable, expectedModified }),
                  (d) => `Moved to ${d?.table}${d?.repriced ? " (re-priced for the new menu)" : ""}`
                )
              }
              className="px-2 py-1 rounded bg-white/15 hover:bg-white/25 text-xs disabled:opacity-40"
            >
              Move
            </button>
          </div>
        </div>
      )}

      <div>
        <label className="block text-xs text-nds-muted mb-1">Merge this order into</label>
        <div className="flex gap-2">
          <select
            value={mergeTarget}
            onChange={(e) => setMergeTarget(e.target.value)}
            className="flex-1 min-w-0 bg-black/40 border border-white/20 rounded px-2 py-1 text-xs"
            data-testid="transfer-merge"
          >
            <option value="">Choose an open order…</option>
            {(opts.orders || []).map((o) => (
              <option key={o.name} value={o.name}>
                {o.table ? `${o.table} · ` : ""}
                {o.name} · {shortUser(o.captain)} · {Number(o.grand_total || 0).toFixed(2)}
              </option>
            ))}
          </select>
          <button
            disabled={busy || !mergeTarget}
            onClick={() => {
              if (!window.confirm(`Merge ${invoice} into ${mergeTarget}? ${invoice} will be closed.`)) return;
              run(() => mergeOrders(invoice, mergeTarget), (d) => `Merged into ${d?.invoice}`);
            }}
            className="px-2 py-1 rounded bg-amber-600/80 hover:bg-amber-500 text-xs disabled:opacity-40"
          >
            Merge
          </button>
        </div>
      </div>
    </div>
  );
}
