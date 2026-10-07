import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePOSStore } from "../store";
import { getOrders } from "../api";
import { parseErrorMessage } from "../lib/errors";
import OrderDetail from "../components/OrderDetail";

const STATUS_BADGE = {
  Unbilled: "bg-amber-500/20 text-amber-300",
  Draft: "bg-sky-500/20 text-sky-300",
  Paid: "bg-emerald-500/20 text-emerald-300",
  Consolidated: "bg-purple-500/20 text-purple-300",
  Return: "bg-red-500/20 text-red-300",
  Cancelled: "bg-gray-500/20 text-gray-300",
  "Unpaid (aggregator)": "bg-orange-500/20 text-orange-300",
};

function money(v) {
  const n = Number(v || 0);
  return n.toFixed(2);
}

function shortUser(u) {
  if (!u) return "";
  return String(u).split("@")[0];
}

export default function OrdersView() {
  const { context } = usePOSStore();
  const tabs = useMemo(() => {
    const t = context?.settings?.tabs;
    return Array.isArray(t) && t.length ? t : ["Draft", "Unbilled"];
  }, [context?.settings?.tabs]);

  const [activeTab, setActiveTab] = useState(tabs.includes("Unbilled") ? "Unbilled" : tabs[0]);
  const [orders, setOrders] = useState([]);
  const [selected, setSelected] = useState(null);
  const [tableFilter, setTableFilter] = useState("");
  const [captainFilter, setCaptainFilter] = useState("");
  const [aggregatorFilter, setAggregatorFilter] = useState("");
  const aggregators = context?.aggregators || [];
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [captains, setCaptains] = useState([]);
  const requestRef = useRef(0);

  useEffect(() => {
    if (!tabs.includes(activeTab)) setActiveTab(tabs[0]);
  }, [tabs, activeTab]);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const loadOrders = useCallback(async () => {
    if (!context?.pos_profile || !activeTab) return;
    const requestId = ++requestRef.current;
    setLoading(true);
    try {
      const res = await getOrders(context.pos_profile, activeTab, {
        table: tableFilter,
        captain: captainFilter,
        search: debouncedSearch,
        aggregator: aggregatorFilter,
      });
      if (requestId !== requestRef.current) return;
      const list = res?.message || res || [];
      setOrders(list);
      setError("");
      setCaptains((prev) => {
        const s = new Set(prev);
        list.forEach((o) => o.captain && s.add(o.captain));
        return Array.from(s).sort();
      });
    } catch (e) {
      if (requestId !== requestRef.current) return;
      setOrders([]);
      setError(parseErrorMessage(e));
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }, [context?.pos_profile, activeTab, tableFilter, captainFilter, debouncedSearch, aggregatorFilter]);

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 15000);
    return () => clearInterval(interval);
  }, [loadOrders]);

  const tables = useMemo(() => (context?.tables || []).map((t) => t.name).sort(), [context?.tables]);

  return (
    <div className="flex flex-1 h-full overflow-hidden text-white">
      <section className="flex-1 min-w-0 p-4 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-xl">Orders</h2>
          <button
            onClick={loadOrders}
            className="px-3 py-1 text-xs rounded bg-white/10 hover:bg-white/20"
            title="Refresh"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-2 mb-3" data-testid="order-tabs">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setSelected(null);
              }}
              className={`px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition ${
                activeTab === tab ? "bg-nds-accent text-nds-green font-bold" : "bg-white/5 hover:bg-white/10 text-gray-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          <input
            type="text"
            placeholder="Search invoice, table or customer…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-[180px] bg-black/20 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-nds-accent"
          />
          <select
            value={tableFilter}
            onChange={(e) => setTableFilter(e.target.value)}
            className="bg-black/30 border border-white/10 rounded px-2 py-2 text-sm"
          >
            <option value="">All tables</option>
            {tables.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            value={captainFilter}
            onChange={(e) => setCaptainFilter(e.target.value)}
            className="bg-black/30 border border-white/10 rounded px-2 py-2 text-sm"
          >
            <option value="">All captains</option>
            {captains.map((c) => (
              <option key={c} value={c}>
                {shortUser(c)}
              </option>
            ))}
          </select>
        </div>

        {aggregators.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3" data-testid="aggregator-filter">
            {[{ customer: "", customer_name: "All orders" }, ...aggregators].map((a) => (
              <button
                key={a.customer || "all"}
                onClick={() => setAggregatorFilter(a.customer)}
                className={`px-2.5 py-1 rounded-full text-xs ${
                  aggregatorFilter === a.customer ? "bg-orange-500 text-white" : "bg-white/5 hover:bg-white/10 text-gray-300"
                }`}
              >
                {a.customer_name || a.customer}
              </button>
            ))}
          </div>
        )}

        {error && <p className="mb-2 text-sm text-red-300">{error}</p>}

        <div className="flex-1 overflow-y-auto space-y-2">
          {loading && orders.length === 0 ? (
            <p className="text-center text-xs text-gray-400 py-8">Loading orders…</p>
          ) : orders.length === 0 ? (
            <p className="text-center text-xs text-gray-400 py-8">No orders found</p>
          ) : (
            orders.map((o) => (
              <button
                type="button"
                key={o.name}
                onClick={() =>
                  o.doctype === "Sales Invoice"
                    ? window.open(`/app/sales-invoice/${encodeURIComponent(o.name)}`, "_blank")
                    : setSelected(o.name)
                }
                className={`w-full text-left p-3 rounded-lg border transition flex justify-between items-center gap-3 ${
                  selected === o.name ? "bg-nds-accent/10 border-nds-accent/50" : "bg-black/20 border-white/5 hover:bg-white/5"
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-bold truncate">
                    {o.daily_order_no ? (
                      <span className="mr-1 text-nds-accent font-semibold" data-testid="order-no">
                        #{o.daily_order_no}
                      </span>
                    ) : null}
                    {o.name}
                    <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] ${STATUS_BADGE[o.order_status] || "bg-white/10"}`}>
                      {o.order_status}
                    </span>
                    {o.aggregator ? (
                      <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-orange-500/20 text-orange-200" data-testid="order-aggregator">
                        {o.aggregator_name || o.aggregator}
                        {o.aggregator_order_id ? ` #${o.aggregator_order_id}` : ""}
                      </span>
                    ) : null}
                  </p>
                  <p className="text-xs text-gray-400 truncate">
                    {o.table ? `${o.table} · ` : ""}
                    {o.order_type || "Take Away"}
                    {o.captain ? ` · ${shortUser(o.captain)}` : ""}
                    {o.posting_time ? ` · ${String(o.posting_time).slice(0, 5)}` : ""}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-bold text-emerald-400">{money(o.rounded_total || o.grand_total)}</p>
                  <p className="text-xs text-gray-400 truncate max-w-[140px]">{o.customer_name || o.customer}</p>
                </div>
              </button>
            ))
          )}
        </div>
      </section>

      {selected ? (
        <OrderDetail
          key={selected}
          invoiceName={selected}
          onClose={() => setSelected(null)}
          onChanged={loadOrders}
          onSelectOrder={setSelected}
        />
      ) : (
        <aside className="w-96 shrink-0 border-l border-white/10 p-5 bg-black/20 hidden md:flex items-center justify-center text-gray-400 text-sm">
          Select an order to view details
        </aside>
      )}
    </div>
  );
}
