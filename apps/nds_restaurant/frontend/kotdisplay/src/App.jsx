import { useEffect, useMemo, useState } from "react";
import { FrappeApp } from "frappe-js-sdk";

const frappe = new FrappeApp(window.location.origin, { useToken: false });
const call = frappe.call();

function getUnitFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  // /kotdisplay/<ProductionUnitName>
  const idx = parts.indexOf("kotdisplay");
  if (idx >= 0 && parts[idx + 1]) return decodeURIComponent(parts[idx + 1]);
  return "";
}

function cardColor(kot) {
  if (kot.kot_type === "Cancelled" || kot.kot_type === "Partially Cancelled") return "bg-red-900/80 border-red-500";
  if (kot.kot_type === "Modified") return "bg-orange-900/70 border-orange-400";
  if (kot.order_type === "Take Away" || kot.order_type === "Delivery") return "bg-blue-900/70 border-blue-400";
  return "bg-white/10 border-white/20";
}

function elapsedMinutes(creation) {
  return Math.floor((Date.now() - new Date(creation).getTime()) / 60000);
}

function parseErrorMessage(e) {
  if (e._server_messages) {
    try {
      const messages = JSON.parse(e._server_messages);
      return messages.map(m => JSON.parse(m).message).join('; ');
    } catch {}
  }
  return e.exception || e.message || String(e);
}

export default function App() {
  const unit = useMemo(() => getUnitFromPath(), []);
  const [ctx, setCtx] = useState(null);
  const [kots, setKots] = useState([]);
  const [error, setError] = useState(null);
  const [units, setUnits] = useState(null);
  const [tick, setTick] = useState(0);
  const [flipped, setFlipped] = useState({});

  async function loadUnits() {
    try {
      const res = await call.get("nds_restaurant.api.kot.get_production_units");
      const data = res.message || res;
      setUnits(data || []);
      if (data && data.length === 1) {
        window.location.href = `/kotdisplay/${encodeURIComponent(data[0].name)}`;
      }
    } catch (e) {
      setError(parseErrorMessage(e));
    }
  }

  async function load() {
    if (!unit) {
      loadUnits();
      return;
    }
    try {
      const res = await call.get("nds_restaurant.api.kot.get_kds_context", {
        production_unit: unit,
      });
      const data = res.message || res;
      setCtx(data);
      setKots(data.kots || []);
      setError(null);
    } catch (e) {
      setError(parseErrorMessage(e));
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(() => setTick((x) => x + 1), 15000);
    const poll = setInterval(load, 8000);
    return () => {
      clearInterval(t);
      clearInterval(poll);
    };
  }, [unit]);

  async function serve(name) {
    try {
      await call.post("nds_restaurant.api.kot.serve_kot", { kot_name: name });
      load();
    } catch (e) {
      setError(parseErrorMessage(e));
    }
  }

  async function confirm(name) {
    try {
      await call.post("nds_restaurant.api.kot.confirm_kot", { kot_name: name });
      load();
    } catch (e) {
      setError(parseErrorMessage(e));
    }
  }

  if (!unit && units !== null) {
    if (units.length === 0) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6">
          <div className="text-center">
            <h1 className="font-display text-3xl mb-2">NDS Kitchen Display</h1>
            <p className="text-red-300">No production units configured</p>
          </div>
        </div>
      );
    }
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center max-w-2xl">
          <h1 className="font-display text-3xl mb-6">NDS Kitchen Display</h1>
          <h2 className="text-xl mb-4">Select Production Unit</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {units.map((u) => (
              <a
                key={u.name}
                href={`/kotdisplay/${encodeURIComponent(u.name)}`}
                className="p-4 rounded-lg bg-white/10 border border-white/20 hover:border-white/40 transition"
              >
                <div className="font-medium">{u.name}</div>
                {u.pos_profile && <div className="text-sm text-gray-400">{u.pos_profile}</div>}
              </a>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center">
          <h1 className="font-display text-3xl mb-2">NDS Kitchen Display</h1>
          <p className="text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  const warning = ctx?.kot_warning_time || 15;

  return (
    <div className="min-h-screen p-4">
      <header className="flex items-center justify-between mb-4">
        <div>
          <h1 className="font-display text-2xl">NDS Kitchen Display</h1>
          <p className="text-gray-400 text-sm">{unit}</p>
        </div>
        <button onClick={load} className="px-3 py-1.5 rounded bg-white/10 text-sm">
          Refresh
        </button>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {kots.map((kot) => {
          const mins = elapsedMinutes(kot.creation);
          const late = mins >= warning;
          const isFlip = flipped[kot.name];
          return (
            <div
              key={kot.name}
              className={`rounded-xl border p-4 ${cardColor(kot)} ${late ? "ring-2 ring-yellow-400" : ""}`}
              onClick={() => setFlipped((f) => ({ ...f, [kot.name]: !f[kot.name] }))}
            >
              {!isFlip ? (
                <>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="font-medium">{kot.order_type}</span>
                    <span className={late ? "text-yellow-300" : "text-gray-300"}>{mins}m</span>
                  </div>
                  <div className="font-display text-xl mb-1">{kot.table || "—"}</div>
                  <div className="text-xs text-gray-300 mb-3">
                    {kot.pos_invoice} · {kot.kot_type} · {kot.user}
                  </div>
                  <ul className="space-y-1 text-sm">
                    {(kot.items || []).map((it, i) => (
                      <li key={i} className="flex justify-between">
                        <span>
                          {it.item_name}
                          {it.comments ? ` — ${it.comments}` : ""}
                        </span>
                        <span>
                          {kot.kot_type.includes("Cancel") ? (
                            <span>
                              {it.qty}/{it.old_qty}
                            </span>
                          ) : (
                            it.qty
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {kot.comments && <p className="mt-2 text-xs text-gray-300">{kot.comments}</p>}
                </>
              ) : (
                <div className="flex flex-col gap-2 h-40 justify-center">
                  {(kot.kot_type === "Cancelled" || kot.kot_type === "Partially Cancelled") ? (
                    <button
                      className="py-3 rounded bg-red-600"
                      onClick={(e) => {
                        e.stopPropagation();
                        confirm(kot.name);
                      }}
                    >
                      Confirm Cancel
                    </button>
                  ) : (
                    <button
                      className="py-3 rounded bg-emerald-600"
                      onClick={(e) => {
                        e.stopPropagation();
                        serve(kot.name);
                      }}
                    >
                      Serve
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!kots.length && (
        <p className="text-center text-gray-500 mt-20">No open KOTs</p>
      )}
      <span className="hidden">{tick}</span>
    </div>
  );
}
