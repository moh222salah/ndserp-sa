import { useEffect, useMemo, useRef, useState } from "react";
import { FrappeApp } from "frappe-js-sdk";
import { io } from "socket.io-client";

const DEFAULT_SOUND = "/assets/nds_restaurant/sounds/kot.mp3";

const frappe = new FrappeApp(window.location.origin, { useToken: false });
const call = frappe.call();

function getUnitFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  // /kotdisplay/<ProductionUnitName>
  const idx = parts.indexOf("kotdisplay");
  if (idx >= 0 && parts[idx + 1]) return decodeURIComponent(parts[idx + 1]);
  return "";
}

function isCancelKot(kot) {
  return kot.kot_type === "Cancelled" || kot.kot_type === "Partially Cancelled";
}

function cardColor(kot) {
  if (isCancelKot(kot)) return "bg-red-900/80 border-red-500";
  if (kot.kot_type === "Transfer") return "bg-teal-900/80 border-teal-400";
  if (kot.kot_type === "Duplicate") return "bg-purple-900/80 border-purple-400";
  if (kot.kot_type === "Modified") return "bg-orange-900/70 border-orange-400";
  if (kot.order_type === "Take Away" || kot.order_type === "Delivery") return "bg-blue-900/70 border-blue-400";
  return "bg-white/10 border-white/20";
}

function elapsedMinutes(creation) {
  return Math.floor((Date.now() - new Date(creation).getTime()) / 60000);
}

function stripHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim();
}

function parseErrorMessage(e) {
  if (e._server_messages) {
    try {
      const messages = JSON.parse(e._server_messages);
      return stripHtml(messages.map((m) => JSON.parse(m).message).join("; "));
    } catch {}
  }
  return stripHtml(e.exception || e.message || String(e));
}

export default function App() {
  const unit = useMemo(() => getUnitFromPath(), []);
  const [ctx, setCtx] = useState(null);
  const [kots, setKots] = useState([]);
  const [error, setError] = useState(null);
  const [units, setUnits] = useState(null);
  const [tick, setTick] = useState(0);
  const [flipped, setFlipped] = useState({});
  // P5-T7: audio alert for new KOTs + realtime nudge (polling stays the fallback)
  const seenRef = useRef(null);
  const audioRef = useRef(null);
  const soundOnRef = useRef(false);
  const [soundOn, setSoundOn] = useState(false);
  const [delayed, setDelayed] = useState({});

  function soundSrc(data) {
    return (data && data.kot_alert_sound) || DEFAULT_SOUND;
  }

  function playAlert(data) {
    if (!soundOnRef.current || !data || !data.kot_audio_alert) return;
    try {
      const src = soundSrc(data);
      if (!audioRef.current || audioRef.current.dataset.src !== src) {
        audioRef.current = new Audio(src);
        audioRef.current.dataset.src = src;
      }
      audioRef.current.currentTime = 0;
      const p = audioRef.current.play();
      if (p && p.catch) p.catch(() => {});
    } catch (e) {
      /* audio is best effort */
    }
  }

  function enableSound() {
    soundOnRef.current = true;
    setSoundOn(true);
    playAlert(ctx);
  }

  function trackNew(data) {
    const list = data.kots || [];
    if (seenRef.current === null) {
      seenRef.current = new Set(list.map((k) => k.name));
      return;
    }
    const fresh = list.filter((k) => !seenRef.current.has(k.name));
    fresh.forEach((k) => seenRef.current.add(k.name));
    if (fresh.length) playAlert(data);
  }

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
      trackNew(data);
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

  useEffect(() => {
    if (!unit) return undefined;
    let socket;
    try {
      const site = window.nds_sitename || window.location.hostname;
      socket = io(`${window.location.origin}/${site}`, {
        path: "/socket.io",
        withCredentials: true,
        reconnectionAttempts: 5,
      });
      socket.on("nds_new_kot", (msg) => {
        if (!msg || !msg.production_unit || msg.production_unit === unit) load();
      });
      socket.on("nds_kot_delay", (msg) => {
        if (msg && msg.production_unit === unit && msg.kot) {
          setDelayed((d) => ({ ...d, [msg.kot]: true }));
        }
      });
    } catch (e) {
      /* realtime is optional; polling keeps the screen fresh */
    }
    return () => {
      if (socket) socket.disconnect();
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
        <div className="flex items-center gap-2">
          {ctx?.kot_audio_alert ? (
            soundOn ? (
              <span className="text-xs text-green-300" data-testid="sound-on">
                Sound on
              </span>
            ) : (
              <button
                onClick={enableSound}
                className="px-3 py-1.5 rounded bg-yellow-400 text-black text-sm font-medium"
                data-testid="enable-sound"
              >
                Enable sound
              </button>
            )
          ) : null}
          <button onClick={load} className="px-3 py-1.5 rounded bg-white/10 text-sm">
            Refresh
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {kots.map((kot) => {
          const mins = elapsedMinutes(kot.creation);
          const late = mins >= warning;
          const isFlip = flipped[kot.name];
          return (
            <div
              key={kot.name}
              className={`rounded-xl border p-4 ${cardColor(kot)} ${
                delayed[kot.name] ? "ring-4 ring-red-500 animate-pulse" : late ? "ring-2 ring-yellow-400" : ""
              }`}
              data-delayed={delayed[kot.name] ? "1" : undefined}
              onClick={() => setFlipped((f) => ({ ...f, [kot.name]: !f[kot.name] }))}
            >
              {!isFlip ? (
                <>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="font-medium">
                      {kot.order_type}
                      {kot.priority != null && (
                        <span
                          className="ml-2 px-1.5 py-0.5 rounded bg-yellow-400 text-black text-[11px] font-bold"
                          data-testid="kot-priority"
                        >
                          P{kot.priority}
                        </span>
                      )}
                    </span>
                    <span className={late ? "text-yellow-300" : "text-gray-300"}>{mins}m</span>
                  </div>
                  {kot.kot_type === "Transfer" && (
                    <div className="inline-block mb-1 px-2 py-0.5 rounded bg-teal-500 text-black text-[11px] font-bold tracking-wide">
                      TRANSFER
                    </div>
                  )}
                  {kot.kot_type === "Duplicate" && (
                    <div
                      className="inline-block mb-1 px-2 py-0.5 rounded bg-purple-400 text-black text-[11px] font-bold tracking-wide"
                      data-testid="duplicate-tag"
                    >
                      DUPLICATE{kot.original_kot ? ` of ${kot.original_kot}` : ""}
                    </div>
                  )}
                  {kot.aggregator && (
                    <div
                      className="inline-block mb-1 px-2 py-0.5 rounded bg-orange-400 text-black text-[11px] font-bold tracking-wide"
                      data-testid="aggregator-tag"
                    >
                      {kot.aggregator}
                      {kot.aggregator_order_id ? ` #${kot.aggregator_order_id}` : ""}
                    </div>
                  )}
                  <div className="font-display text-xl mb-1">{kot.table || "—"}</div>
                  {kot.customer_name && (
                    <div className="text-sm text-gray-200 mb-1" data-testid="kot-customer">
                      {kot.customer_name}
                    </div>
                  )}
                  <div className="text-xs text-gray-300 mb-3">
                    {kot.daily_order_no ? `#${kot.daily_order_no} · ` : ""}
                    {kot.pos_invoice} · {kot.kot_type} · {kot.user}
                  </div>
                  <ul className="space-y-1 text-sm">
                    {(kot.items || []).map((it, i) => (
                      <li
                        key={i}
                        className={`flex justify-between ${it.is_addon ? "pl-4 text-gray-300" : ""}`}
                      >
                        <span>
                          {it.indicate_in_kds && it.serving_priority != null && !it.is_addon ? (
                            <span
                              className="mr-1 px-1 rounded bg-yellow-400/90 text-black text-[10px] font-bold"
                              data-testid="course-chip"
                            >
                              P{it.serving_priority} {it.course}
                            </span>
                          ) : null}
                          {it.is_addon ? "+ " : ""}
                          {it.item_name}
                          {it.comments ? ` — ${it.comments}` : ""}
                          {it.cancelled_qty ? ` (−${it.cancelled_qty})` : ""}
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
                  {isCancelKot(kot) ? (
                    ctx?.can_verify ? (
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
                      <p className="py-3 text-center text-sm text-red-200" data-testid="awaiting-manager">
                        Awaiting manager
                      </p>
                    )
                  ) : kot.kot_type === "Transfer" || kot.kot_type === "Duplicate" ? (
                    <button
                      className={`py-3 rounded ${kot.kot_type === "Duplicate" ? "bg-purple-600" : "bg-teal-600"}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        serve(kot.name);
                      }}
                    >
                      Acknowledge
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
