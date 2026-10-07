frappe.pages["gas_station_dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Gas Station Dashboard"),
		single_column: true,
	});

	const dash = new GasStationDashboard(page);
	wrapper.gas_dashboard = dash;
};

frappe.pages["gas_station_dashboard"].on_page_show = function (wrapper) {
	if (wrapper.gas_dashboard) wrapper.gas_dashboard.refresh();
};

class GasStationDashboard {
	constructor(page) {
		this.page = page;
		this.station = null;
		this.$body =$(`<div class="gs-dash"></div>`).appendTo(page.main);
		this._inject_styles();
		this._make_controls();
		this.refresh();
		this._rt = frappe.realtime.on("gas_station_update", () => this._debounced_refresh());
		this._timer = setInterval(() => this.refresh(), 15000);
	}

	_make_controls() {
		this.station_field = this.page.add_field({
			fieldname: "station",
			label: __("Station"),
			fieldtype: "Link",
			options: "Gas Station",
			change: () => {
				this.station = this.station_field.get_value() || null;
				this.refresh();
			},
		});
		this.range_field = this.page.add_field({
			fieldname: "range_preset",
			label: __("Period"),
			fieldtype: "Select",
			options: ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "All Time", "Custom"].join("\n"),
			default: "Last 7 Days",
			change: () => this._apply_preset(),
		});
		this.from_field = this.page.add_field({
			fieldname: "from_date",
			label: __("From"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -6),
			change: () => {
				if (this.range_field.get_value() !== "Custom") {
					this._silent = true;
					this.range_field.set_value("Custom");
					this._silent = false;
				}
				this.refresh();
			},
		});
		this.to_field = this.page.add_field({
			fieldname: "to_date",
			label: __("To"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			change: () => {
				if (this.range_field.get_value() !== "Custom") {
					this._silent = true;
					this.range_field.set_value("Custom");
					this._silent = false;
				}
				this.refresh();
			},
		});
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
	}

	_apply_preset() {
		if (this._silent) return;
		const today = frappe.datetime.get_today();
		const preset = this.range_field.get_value();
		const set = (from, to) => {
			this._silent = true;
			this.from_field.set_value(from);
			this.to_field.set_value(to);
			this._silent = false;
		};
		switch (preset) {
			case "Today":
				set(today, today);
				break;
			case "Yesterday": {
				const y = frappe.datetime.add_days(today, -1);
				set(y, y);
				break;
			}
			case "Last 7 Days":
				set(frappe.datetime.add_days(today, -6), today);
				break;
			case "Last 30 Days":
				set(frappe.datetime.add_days(today, -29), today);
				break;
			case "All Time":
				set(null, null);
				break;
			case "Custom":
				this.refresh();
				return;
		}
		this.refresh();
	}

	_debounced_refresh() {
		clearTimeout(this._dt);
		this._dt = setTimeout(() => this.refresh(), 800);
	}

	refresh() {
		const from = this.from_field ? this.from_field.get_value() : null;
		const to = this.to_field ? this.to_field.get_value() : null;
		const all_time = this.range_field && this.range_field.get_value() === "All Time";
		frappe.call({
			method: "gas_station.gas_station.dashboard.get_dashboard_data",
			args: {
				station: this.station,
				from_date: all_time ? null : from,
				to_date: all_time ? null : to,
				all_time: all_time ? 1 : 0,
			},
			callback: (r) => r.message && this.render(r.message),
		});
	}

	render(d) {
		this.$body.empty();
		if (d.demo) {
			$(`<div class="gs-demo-banner">DEMO — Mock PTS data</div>`).appendTo(this.$body);
		}
		this._render_kpis(d.kpis);
		this._section("Pump Monitor");
		this._render_pumps(d.pumps);
		this._section("Tank Monitor");
		this._render_tanks(d.tanks);
		const $cols =$(`<div class="gs-cols"></div>`).appendTo(this.$body);
		this._render_alerts(d.alerts, $cols);
		this._render_controllers(d.controllers, $cols);
		this._section("Latest Transactions");
		this._render_txns(d.transactions);
		$(`<div class="gs-updated text-muted">Updated ${frappe.datetime.str_to_user(d.generated_at)}</div>`).appendTo(this.$body);
	}

	_section(t) {
		$(`<h4 class="gs-h">${__(t)}</h4>`).appendTo(this.$body);
	}

	_render_kpis(k) {
		const cards = [
			["Revenue", fmt_money(k.revenue), "revenue"],
			["Fuel Sold (L)", fmt_num(k.fuel_sold), "fuel"],
			["Transactions", fmt_num(k.transactions), "txn"],
			["Active Pumps", k.active_pumps, "pumps"],
			["Open Alerts", k.open_alerts, k.open_alerts ? "alert" : "ok"],
			["Tank Stock (L)", fmt_num(k.tank_stock), "tank"],
			["Integration", k.integration, k.integration_ok ? "ok" : "alert"],
		];
		const $g =$(`<div class="gs-kpis"></div>`).appendTo(this.$body);
		cards.forEach(([label, val, cls]) => {
			$(`<div class="gs-kpi gs-${cls}">
				<div class="gs-kpi-val">${val}</div>
				<div class="gs-kpi-label">${__(label)}</div>
			</div>`).appendTo($g);
		});
	}

	_render_pumps(pumps) {
		const $g =$(`<div class="gs-grid"></div>`).appendTo(this.$body);
		if (!pumps.length) return empty($g);
		pumps.forEach((p) => {
			$(`<div class="gs-card">
				<div class="gs-card-head">
					<b>${frappe.utils.escape_html(p.pump)}</b>
					${badge(p.status)} ${comm(p.communication_status)}
				</div>
				<div class="gs-kv"><span>Fuel</span><b>${p.current_fuel_grade || "—"}</b></div>
				<div class="gs-kv"><span>Nozzle</span><b>${p.current_nozzle || "—"}</b></div>
				<div class="gs-kv"><span>Volume</span><b>${orDash(p.current_volume, "L")}</b></div>
				<div class="gs-kv"><span>Amount</span><b>${orDash(p.current_amount)}</b></div>
				<div class="gs-kv"><span>Flow</span><b>${orDash(p.flow_rate, "L/min")}</b></div>
				<div class="gs-kv"><span>Totalizer</span><b>${orDash(p.totalizer_volume, "L")}</b></div>
				<div class="gs-ago text-muted">${ago(p.last_updated_at)}</div>
			</div>`).appendTo($g);
		});
	}

	_render_tanks(tanks) {
		const $g =$(`<div class="gs-grid"></div>`).appendTo(this.$body);
		if (!tanks.length) return empty($g);
		tanks.forEach((t) => {
			const pct = Math.max(0, Math.min(100, t.fill_percentage || 0));
			const low = pct < 20;
			$(`<div class="gs-card">
				<div class="gs-card-head">
					<b>${frappe.utils.escape_html(t.tank)}</b>
					${badge(t.status)} ${comm(t.communication_status)}
				</div>
				<div class="gs-bar"><div class="gs-bar-fill ${low ? "low" : ""}" style="width:${pct}%"></div></div>
				<div class="gs-kv"><span>Fill</span><b>${orDash(t.fill_percentage, "%")}</b></div>
				<div class="gs-kv"><span>Volume</span><b>${orDash(t.product_volume, "L")}</b></div>
				<div class="gs-kv"><span>Temp</span><b>${orDash(t.temperature, "°C")}</b></div>
				<div class="gs-kv"><span>Water</span><b>${orDash(t.water_level, "mm")}</b></div>
				<div class="gs-ago text-muted">${ago(t.last_updated_at)}</div>
			</div>`).appendTo($g);
		});
	}

	_render_alerts(a, $cols) {
		const $c =$(`<div class="gs-panel"><h5>${__("Alerts")}
			<span class="gs-pill crit">${a.critical} ${__("Critical")}</span>
			<span class="gs-pill warn">${a.warning} ${__("Warning")}</span></h5></div>`).appendTo($cols);
		const $l =$(`<div class="gs-list"></div>`).appendTo($c);
		if (!a.recent.length) return empty($l);
		a.recent.forEach((x) => {
			$(`<div class="gs-li">
				${sev(x.severity)}
				<div class="gs-li-main"><b>${x.alert_type}</b>
				<div class="text-muted">${x.message || x.equipment_reference || ""}</div></div>
				<div class="text-muted small">${ago(x.occurred_at)}</div>
			</div>`).appendTo($l);
		});
	}

	_render_controllers(rows, $cols) {
		const $c =$(`<div class="gs-panel"><h5>${__("Connection Status")}</h5></div>`).appendTo($cols);
		const $l =$(`<div class="gs-list"></div>`).appendTo($c);
		if (!rows.length) return empty($l);
		rows.forEach((r) => {
			const ok = r.connection_status === "Connected";
			$(`<div class="gs-li">
				<span class="gs-dot ${ok ? "up" : "down"}"></span>
				<div class="gs-li-main"><b>${r.controller_name || r.name}</b>
				<div class="text-muted small">${r.station || ""}</div></div>
				<div class="text-muted small">${r.connection_status}<br>${orDash(r.latency_ms, "ms")}</div>
			</div>`).appendTo($l);
		});
	}

	_render_txns(rows) {
		const $t =$(`<table class="table gs-table"><thead><tr>
			<th>Time</th><th>Station</th><th>Pump</th><th>Nozzle</th><th>Fuel</th>
			<th class="text-right">Volume</th><th class="text-right">Amount</th><th>Status</th>
			</tr></thead><tbody></tbody></table>`).appendTo(this.$body);
		const $b =$t.find("tbody");
		if (!rows.length) { $b.append(`<tr><td colspan="8" class="text-muted text-center">No transactions</td></tr>`); return; }
		rows.forEach((x) => {
			$(`<tr>
				<td>${frappe.datetime.str_to_user(x.start_datetime)}</td>
				<td>${x.station || ""}</td><td>${x.pump || ""}</td><td>${x.nozzle || ""}</td>
				<td>${x.fuel_grade || ""}</td>
				<td class="text-right">${orDash(x.volume, "L")}</td>
				<td class="text-right">${orDash(x.amount)}</td>
				<td>${badge(x.processing_status)}</td>
			</tr>`).appendTo($b);
		});
	}

	_inject_styles() {
		if (document.getElementById("gs-dash-styles")) return;
		const css = `
		.gs-dash{padding:4px 2px}
		.gs-demo-banner{background:#fef3c7;color:#92400e;border:1px solid #fde68a;padding:6px 12px;border-radius:8px;font-weight:600;margin-bottom:12px;display:inline-block}
		.gs-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:8px}
		.gs-kpi{background:var(--card-bg,#fff);border:1px solid var(--border-color,#e5e7eb);border-radius:12px;padding:14px 16px}
		.gs-kpi-val{font-size:22px;font-weight:700}
		.gs-kpi-label{color:var(--text-muted,#6b7280);font-size:12px;margin-top:2px}
		.gs-alert .gs-kpi-val{color:#dc2626}.gs-ok .gs-kpi-val{color:#16a34a}
		.gs-h{margin:18px 0 8px}
		.gs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
		.gs-card{background:var(--card-bg,#fff);border:1px solid var(--border-color,#e5e7eb);border-radius:12px;padding:12px 14px}
		.gs-card-head{display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap}
		.gs-kv{display:flex;justify-content:space-between;font-size:13px;padding:1px 0}
		.gs-kv span{color:var(--text-muted,#6b7280)}
		.gs-ago{font-size:11px;margin-top:6px}
		.gs-bar{height:8px;background:#eef2f7;border-radius:6px;overflow:hidden;margin:4px 0 8px}
		.gs-bar-fill{height:100%;background:#2563eb}.gs-bar-fill.low{background:#dc2626}
		.gs-cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px}
		@media(max-width:800px){.gs-cols{grid-template-columns:1fr}}
		.gs-panel{background:var(--card-bg,#fff);border:1px solid var(--border-color,#e5e7eb);border-radius:12px;padding:12px 14px}
		.gs-panel h5{margin:0 0 8px}
		.gs-list{display:flex;flex-direction:column;gap:6px}
		.gs-li{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border-color,#f1f5f9)}
		.gs-li-main{flex:1}
		.gs-pill{font-size:11px;padding:1px 8px;border-radius:20px;margin-left:6px}
		.gs-pill.crit{background:#fee2e2;color:#b91c1c}.gs-pill.warn{background:#fef3c7;color:#92400e}
		.gs-badge{font-size:11px;padding:1px 8px;border-radius:20px;background:#e5e7eb;color:#374151}
		.gs-badge.Dispensing,.gs-badge.Processed{background:#dcfce7;color:#166534}
		.gs-badge.Offline,.gs-badge.Failed,.gs-badge.Error{background:#fee2e2;color:#b91c1c}
		.gs-badge.Idle,.gs-badge.Received{background:#dbeafe;color:#1e40af}
		.gs-comm{font-size:10px;padding:1px 6px;border-radius:20px}
		.gs-comm.Live{background:#dcfce7;color:#166534}.gs-comm.Stale{background:#fef3c7;color:#92400e}
		.gs-comm.Offline{background:#fee2e2;color:#b91c1c}
		.gs-dot{width:10px;height:10px;border-radius:50%}.gs-dot.up{background:#16a34a}.gs-dot.down{background:#dc2626}
		.gs-sev{width:8px;height:8px;border-radius:50%}
		.gs-sev.Critical{background:#dc2626}.gs-sev.Warning{background:#f59e0b}.gs-sev.Info{background:#3b82f6}
		.gs-table{margin-top:4px}.gs-updated{margin-top:12px;font-size:11px}
		.gs-empty{color:var(--text-muted,#9ca3af);padding:14px;text-align:center;font-size:13px}`;
		$(`<style id="gs-dash-styles">${css}</style>`).appendTo(document.head);
	}
}

function fmt_money(v) { return format_currency(v || 0); }
function fmt_num(v) { return frappe.format(v || 0, { fieldtype: "Float", precision: 0 }); }
function orDash(v, unit) {
	if (v === null || v === undefined || v === "") return "—";
	const n = frappe.format(v, { fieldtype: "Float", precision: 2 });
	return unit ? `${n} ${unit}` : n;
}
function badge(s) { return s ? `<span class="gs-badge ${s}">${s}</span>` : ""; }
function comm(s) { return s ? `<span class="gs-comm ${s}">${s}</span>` : ""; }
function sev(s) { return `<span class="gs-sev ${s}"></span>`; }
function ago(dt) { return dt ? frappe.datetime.comment_when(dt) : "—"; }
function empty($el) {$el.append(`<div class="gs-empty">No data yet</div>`); }
