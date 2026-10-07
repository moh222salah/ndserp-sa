/**
 * Quick Entry: hydrate a doc that was handed in as a plain boot record.
 *
 * The bug this fixes
 * ------------------
 * Right-clicking a tile on the apps screen and choosing "Edit" runs
 * (frappe/desk/page/desktop/desktop.js):
 *
 *     frappe.ui.form.make_quick_entry("Desktop Icon", cb, init, icon_data, null)
 *
 * where `icon_data` is an entry of `frappe.boot.desktop_icons` — a plain object
 * built by a query-builder SELECT of sixteen columns, decorated by the desktop
 * page with a synthetic `child_icons` array. It is NOT a `locals` document, so:
 *
 *   • it has no `doctype`, and `QuickEntryForm.insert()` POSTs it verbatim to
 *     `frappe.client.save`, which does `frappe.get_doc(doc)` and raises
 *     `ValueError: "doctype" is a required key`. Uploading an icon image and
 *     pressing Save is the shortest path to it — the file uploads, the save
 *     dies, and the icon never changes.
 *   • it is only a partial row. Even with a `doctype` bolted on, saving it
 *     would silently blank every column the SELECT left out — on Desktop Icon
 *     that is `roles`, `sidebar` and `standard`.
 *
 * The fix
 * -------
 * Before the dialog is built, if `doc` names an existing record but carries no
 * `doctype`, fetch the real document and use that instead. The dialog then
 * edits a complete, correctly-typed doc and saves like any other.
 *
 * Safety properties
 *   • narrowly gated — a doc that already has a `doctype` (every other caller
 *     in the framework, including new-doc flows) takes the original path
 *     untouched, synchronously.
 *   • fail-safe — if the fetch fails we still stamp the `doctype` on and carry
 *     on, so the dialog degrades to today's behaviour rather than not opening.
 *   • idempotent — the prototype is marked, so a second install is a no-op.
 */

const PATCH_FLAG = "__amtHydratesPartialDoc";

function patch() {
	const QuickEntryForm = window.frappe?.ui?.form?.QuickEntryForm;
	if (!QuickEntryForm || QuickEntryForm.prototype[PATCH_FLAG]) return !!QuickEntryForm;

	QuickEntryForm.prototype[PATCH_FLAG] = true;
	const original_setup = QuickEntryForm.prototype.setup;

	QuickEntryForm.prototype.setup = function () {
		const doc = this.doc;
		// `__islocal` marks an unsaved doc built by frappe.model.get_new_doc —
		// there is nothing on the server to fetch for one of those.
		const is_partial = doc && !doc.doctype && doc.name && !doc.__islocal;
		if (!is_partial) return original_setup.call(this);

		return frappe.db
			.get_doc(this.doctype, doc.name)
			.then((full) => {
				if (full && full.doctype) this.doc = full;
				else this.doc.doctype = this.doctype;
			})
			.catch(() => {
				this.doc.doctype = this.doctype;
			})
			.then(() => original_setup.call(this));
	};

	return true;
}

export const quickEntryFix = {
	install() {
		// The desk bundle defines QuickEntryForm before app_include_js runs, so
		// this normally lands on the first try. The ready fallback covers a load
		// order we do not control (e.g. an app injecting its own bundle earlier).
		if (patch()) return;
		$(document).ready(patch);
	},
};
