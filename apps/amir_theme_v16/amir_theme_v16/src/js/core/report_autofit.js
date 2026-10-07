/**
 * Query-report column auto-fit.
 *
 * ERPNext query reports ship FIXED per-column widths (frappe-datatable
 * `layout:"fixed"`), tuned for English and blind to the actual data: a code
 * column gets 180px whether it holds "1310" or "Cost of Goods Sold - ED - 5111",
 * so some columns truncate while neighbours sit half-empty. This reproduces the
 * library's own "perfect width" logic (its dbl-click-on-resize-handle feature)
 * for EVERY column, once per render, so each column is as wide as its widest
 * value and no wider.
 *
 * Safety properties:
 *   • uses only the datatable's public column API (updateColumn +
 *     setColumnHeaderWidth + setColumnWidth), so header and body stay in sync
 *     and the theme's `.dt-scrollable{width:100%}` fix keeps holding
 *   • width is measured in the REAL cell font via a hidden `.dt-cell__content`
 *     (canvas under-measures Arabic/tabular text and would truncate) and only
 *     the few longest-by-length candidates per column are DOM-measured, so cost
 *     stays flat even on large reports
 *   • never shrinks below a value's own width → it cannot hide data
 *   • wrapped end-to-end in try/catch: a failure leaves frappe's own widths
 *     untouched, never breaking the report
 */

const NUMERIC = new Set(["Currency", "Float", "Int", "Percent"]);

// Cell padding/border slack, floor, and per-type ceilings (px).
const PAD = 30;
const MIN = 76;
const MAX_TEXT = 340;
const MAX_NUM = 190;

// Candidate scan bounds — keep the O(rows) work cheap on huge reports.
const MAX_SCAN = 20000;   // rows scanned for "longest" candidates
const CANDIDATES = 8;     // longest-by-length cells DOM-measured per column

// Report columns whose VALUE is a doctype name / enum rendered raw — e.g. GL/AP
// `voucher_type` = "Purchase Invoice", `party_type` = "Supplier". Frappe leaves
// these untranslated in the datatable even when an Arabic translation exists, so
// an Arabic report showed English doctype names in its cells. We translate the
// DISPLAY only (via the column's format fn), never the stored value, so Dynamic
// Link columns that key off these fields (voucher_no→voucher_type,
// party→party_type) keep resolving to the right doctype.
const DOCTYPE_NAME_FIELDS = new Set([
	"voucher_type", "party_type", "reference_type", "against_voucher_type",
	"reference_doctype", "dt", "link_doctype", "entry_type", "payment_type",
	"child_doctype", "document_type", "reference_document_type",
]);

// Wrap a doctype-name column's format fn so its cell text renders through __().
// Applied in prepare_columns (BEFORE the datatable is built), so the very first
// render is already translated — no re-render, so no clash with the datatable's
// natural-width pass. Display-only: the underlying value is untouched, so Dynamic
// Link columns keyed off this field still resolve to the right doctype.
function wrapColumnFormat(col) {
	if (!col || !DOCTYPE_NAME_FIELDS.has(col.fieldname) || col.__amtI18n) return;
	const orig = typeof col.format === "function" ? col.format : null;
	col.format = function (value, row, column, data, filter) {
		const tv = value != null && value !== "" && typeof __ === "function"
			? __(String(value))
			: value;
		return orig
			? orig.call(this, tv, row, column, data, filter)
			: tv;
	};
	col.__amtI18n = true;
}

function autofit(dt) {
	const dm = dt && dt.datamanager;
	if (!dm || typeof dm.getColumns !== "function") return;

	const columns = dm.getColumns();
	const rows = dm.rows || [];
	if (!columns.length || !rows.length) return;

	// Measure in the true cell font: a hidden node that inherits `.dt-cell__content`
	// styling from inside the live datatable. scrollWidth is exact (font, shaping,
	// tabular figures) where a canvas is not.
	const host =
		dt.bodyScrollable ||
		document.querySelector(".datatable .dt-scrollable") ||
		document.querySelector(".datatable");
	if (!host) return;

	const meas = document.createElement("div");
	meas.className = "dt-cell__content";
	meas.style.cssText =
		"position:absolute;visibility:hidden;pointer-events:none;" +
		"white-space:nowrap;width:auto;min-width:0;max-width:none;" +
		"padding:0;border:0;left:-99999px;top:0;";
	host.appendChild(meas);

	const scratch = document.createElement("div");
	const strip = (t) => {
		t = t == null ? "" : String(t);
		// Only pay for HTML parsing when the value actually carries markup (links).
		if (t.indexOf("<") >= 0) {
			scratch.innerHTML = t;
			t = scratch.textContent || "";
		}
		return t.trim();
	};
	const textWidth = (t) => {
		meas.textContent = t || "";
		return meas.scrollWidth;
	};

	const scanLimit = Math.min(rows.length, MAX_SCAN);

	try {
		columns.forEach((col) => {
			const i = col.colIndex;

			// Row-number column: frappe fixes it at ~39px, which clips the moment
			// the count reaches two digits ("10" → "1…"). Fit it to the largest
			// index with tight padding and a low ceiling so it stays compact.
			if (i === 0 || col.id === "_rowIndex") {
				const w = Math.round(
					Math.min(90, Math.max(34, textWidth(String(rows.length)) + 16))
				);
				dm.updateColumn(i, { width: w });
				dt.columnmanager.setColumnHeaderWidth(i);
				dt.columnmanager.setColumnWidth(i);
				return;
			}

			// Header floor: the widest single word, so a title wraps cleanly at a
			// space (headers are 2-line clamped in CSS) without a mid-word break.
			let floor = 0;
			strip(col.content != null ? col.content : col.name || "")
				.split(/\s+/)
				.forEach((w) => {
					const x = textWidth(w);
					if (x > floor) floor = x;
				});

			// Cheap O(rows) pass: collect raw cell strings, keep the longest few by
			// length, then DOM-measure only those (length ~ width for our content).
			const raw = [];
			for (let r = 0; r < scanLimit; r++) {
				const cell = rows[r][i];
				if (!cell) continue;
				raw.push(cell.html != null ? cell.html : cell.content);
			}
			raw.sort((a, b) => String(b).length - String(a).length);

			// Doctype-name columns render translated (see wrapColumnFormat), so
			// measure the TRANSLATED text or the column would be sized to the shorter
			// English value and clip the Arabic ("فاتورة…").
			const i18n = DOCTYPE_NAME_FIELDS.has(col.fieldname);
			let contentMax = 0;
			for (let k = 0; k < Math.min(CANDIDATES, raw.length); k++) {
				let t = strip(raw[k]);
				if (i18n && t) t = __(t);
				const w = textWidth(t);
				if (w > contentMax) contentMax = w;
			}

			const ceil = NUMERIC.has(col.fieldtype) ? MAX_NUM : MAX_TEXT;
			const width = Math.round(
				Math.min(ceil, Math.max(MIN, Math.max(contentMax, floor) + PAD))
			);

			dm.updateColumn(i, { width });
			dt.columnmanager.setColumnHeaderWidth(i);
			dt.columnmanager.setColumnWidth(i);
		});
	} finally {
		meas.remove();
	}

	// setColumnWidth already applied + header/body-synced every column, so the
	// layout is complete here. setDimensions() would only re-run the datatable's
	// natural-width pass, which on some reports (e.g. AP, many columns) throws
	// mid-render reading `.naturalWidth` off a transiently-missing column. Attempt
	// it for the reports where it helps, but never let its internal race surface.
	if (typeof dt.setDimensions === "function") {
		try { dt.setDimensions(); } catch (e) { /* widths already set; ignore */ }
	}
}

// Patch the QueryReport prototype ONCE. render_datatable is the single render
// entry for both first paint and every filter refresh, so fitting right after it
// covers all cases with no DOM observer to leak or loop.
function ensurePatched() {
	const QR = window.frappe && frappe.views && frappe.views.QueryReport;
	if (!QR || QR.prototype.__amtAutofitPatched) return;

	// (1) Translate doctype-name cells at column-prep time, so the first render is
	// already Arabic (no re-render → no clash with the natural-width pass).
	const origPrepare = QR.prototype.prepare_columns;
	if (typeof origPrepare === "function") {
		QR.prototype.prepare_columns = function (columns) {
			const prepared = origPrepare.call(this, columns);
			try {
				if (Array.isArray(prepared)) prepared.forEach(wrapColumnFormat);
			} catch (e) {
				/* leave columns untranslated rather than break the report */
			}
			return prepared;
		};
	}

	// (2) Fit columns to content after each render. render_datatable is the single
	// render entry for both first paint and every filter refresh.
	const origRender = QR.prototype.render_datatable;
	if (typeof origRender !== "function") return;

	QR.prototype.render_datatable = function (...args) {
		const result = origRender.apply(this, args);
		// Let the datatable settle a frame, then fit. Never let a fit error
		// bubble into frappe's render path.
		setTimeout(() => {
			try {
				autofit(this.datatable);
			} catch (e) {
				// eslint-disable-next-line no-console
				console.error("[amir_theme] report autofit failed:", e);
			}
		}, 50);
		return result;
	};

	QR.prototype.__amtAutofitPatched = true;
}

export const reportAutofit = {
	mount() {
		// QueryReport is bundled lazily — try now, and again whenever a route
		// change may have just loaded it.
		ensurePatched();
		$(document).on("page-change", ensurePatched);
	},
};
