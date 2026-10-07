/**
 * SMART SUBMIT ACTIONS — one extra, clearly-styled button per document state
 * on every "Is Submittable" doctype:
 *
 *   docstatus 0 (Draft)     → "Save & Final Submit"   (green)
 *   docstatus 1 (Submitted) → "Revert to Draft"        (amber)
 *                            → "Cancel & Delete"        (red)
 *
 * Hard rules, in priority order:
 *   1. Never shown when the doctype has an ACTIVE Workflow — a workflow
 *      already owns the draft→submit transition (and often intermediate
 *      states in between); a second button doing the same thing would race
 *      or fight it. This is verified with a real server call, never assumed.
 *   2. Never shown unless the acting user actually holds the underlying
 *      Frappe role permission for that action (Submit / Cancel / Delete /
 *      Create) — reuses the exact checkboxes in Role Permission Manager,
 *      no new permission concept invented. Re-verified server-side too.
 *   3. Every action confirms first, in the user's own language.
 *
 * Same defensive posture as report_autofit.js / erpnext16_theme's
 * form_actions.js: patches frappe.ui.form.Form.prototype.refresh exactly
 * once, and bails immediately if a grid row is open or the page is frozen —
 * touching the toolbar mid-grid-operation is the known Child Table trap.
 */

const BTN_CLASS = "amt-smart-btn";

function L(ar, en) {
	const lang = document.documentElement.getAttribute("lang");
	return lang === "ar" ? ar : en;
}

function toast(message, indicator) {
	try {
		frappe.show_alert({ message, indicator: indicator || "blue" }, 5);
	} catch (e) {
		/* never let a toast failure surface */
	}
}

// ---- gating info: one real server call per doctype, then cached ----------
// has_workflow has no boot-time equivalent at all, and per-doctype can_*
// permission flags may not be warm yet the first time a doctype is opened —
// frappe.boot.user.can_submit/can_cancel/... IS reliable once populated, but
// asking the server once and caching is simpler and just as cheap.

const gatingCache = new Map(); // doctype -> Promise<{has_workflow, can_submit, can_cancel, can_delete, can_create}>

function getGating(doctype) {
	if (!gatingCache.has(doctype)) {
		gatingCache.set(
			doctype,
			frappe
				.call("amir_theme_v16.api.smart_actions.can_show_smart_actions", { doctype })
				.then((r) => r.message || {})
				.catch(() => ({ has_workflow: true })) // fail closed: hide buttons on error
		);
	}
	return gatingCache.get(doctype);
}

// ---- the three actions ----------------------------------------------------

function actSaveSubmit(frm) {
	frappe.confirm(
		L(
			`سيتم <b>حفظ</b> المستند ثم <b>اعتماده نهائياً</b>. لا يمكن التراجع عن هذه الخطوة إلا يدوياً. متابعة؟`,
			`This will <b>save</b> the document and then <b>submit it for good</b>. Continue?`
		),
		() => {
			try {
				frm.savesubmit();
			} catch (e) {
				toast(L("تعذّر الحفظ والاعتماد", "Could not save & submit"), "red");
				console.warn("[amt] save&submit", e);
			}
		}
	);
}

function actRevertToDraft(frm) {
	const dt = frm.doctype;
	const dn = frm.docname;
	frappe.confirm(
		L(
			`سيتم <b>إلغاء اعتماد</b> المستند ${frappe.utils.escape_html(dn)} ثم إعادته <b>مسودة قابلة للتعديل</b> بنفس الرقم التسلسلي. متابعة؟`,
			`This will <b>cancel</b> ${frappe.utils.escape_html(dn)} and reopen it as an <b>editable draft</b> under the same serial number. Continue?`
		),
		() => {
			frappe.call({
				method: "amir_theme_v16.api.smart_actions.revert_to_draft",
				args: { doctype: dt, docname: dn },
				freeze: true,
				freeze_message: L("جارٍ الرجوع إلى المسودة…", "Reverting to draft…"),
			})
				.then((r) => {
					toast(L("تم الرجوع إلى المسودة", "Reverted to draft"), "green");
					const name = (r.message && r.message.name) || dn;
					frappe.model.clear_doc(dt, dn);
					frappe.set_route("Form", dt, name);
				})
				.catch((err) => {
					toast(
						L("تعذّر الرجوع إلى المسودة — لم يتغيّر المستند", "Could not revert — the document is unchanged"),
						"red"
					);
					console.warn("[amt] revert_to_draft", err);
				});
		}
	);
}

function actCancelDelete(frm) {
	const dt = frm.doctype;
	const dn = frm.docname;
	frappe.confirm(
		L(
			`سيتم <b>إلغاء</b> المستند ${frappe.utils.escape_html(dn)} ثم <b>حذفه نهائياً</b>. هذا الإجراء لا يمكن التراجع عنه. متابعة؟`,
			`This will <b>cancel</b> ${frappe.utils.escape_html(dn)} and then <b>permanently delete</b> it. This cannot be undone. Continue?`
		),
		() => {
			frm.savecancel(
				undefined,
				() => {
					frappe
						.call({
							method: "frappe.client.delete",
							args: { doctype: dt, name: dn },
							freeze: true,
							freeze_message: L("جارٍ الحذف…", "Deleting…"),
						})
						.then(() => {
							toast(L("تم الإلغاء والحذف بنجاح", "Cancelled & deleted"), "green");
							frappe.set_route("List", dt);
						})
						.catch((err) => {
							toast(
								L("تم الإلغاء، لكن تعذّر الحذف", "Cancelled, but delete failed"),
								"orange"
							);
							console.warn("[amt] cancel-delete", err);
						});
				},
				() => toast(L("تعذّر الإلغاء", "Cancel failed"), "red")
			);
		}
	);
}

// ---- button injection ------------------------------------------------------

function clearOurButtons(frm) {
	try {
		frm.page.wrapper.find("." + BTN_CLASS).remove();
	} catch (e) {}
}

function addSmartButton(frm, label, variant, handler) {
	let $btn;
	try {
		$btn = frm.add_custom_button(label, () => handler(frm));
	} catch (e) {
		return;
	}
	if (!$btn || !$btn.length) return;
	$btn.removeClass("btn-default").addClass(BTN_CLASS).attr("data-variant", variant);
}

function decorate(frm) {
	if (!frm || !frm.doc || !frm.meta) return;

	// HARD GUARD — identical reasoning to erpnext16_theme's form_actions.js:
	// never touch the toolbar while a grid row editor is open or the page is
	// frozen. Doing so mid-grid-operation is the historic Child Table trap.
	try {
		if (
			document.querySelector(".grid-row-open") ||
			document.querySelector("#freeze") ||
			(window.frappe && frappe.dom && frappe.dom.freeze_count > 0)
		) {
			return;
		}
	} catch (e) {
		return;
	}

	clearOurButtons(frm);

	if (!frm.meta.is_submittable) return;

	const ds = frm.doc.docstatus;
	if (ds !== 0 && ds !== 1) return; // nothing to add once cancelled

	// A brand-new, never-saved document is allowed here on purpose: the
	// button's own frm.savesubmit() already runs the full save flow first
	// (mandatory-field checks, before_save/before_submit, its own native
	// "Permanently Submit?" confirm) exactly like it would for an existing
	// draft — frappe.desk.form.save.savedocs handles insert+submit as one
	// call regardless of whether the doc already exists. Frappe's own
	// primary Submit button hides on new docs as a UX choice (can_submit()
	// requires !__islocal), not a technical limitation; this button is
	// deliberately the one-click shortcut across that boundary.

	const doctype = frm.doctype;
	const docname = frm.docname;

	getGating(doctype).then((g) => {
		// The gating call is async — bail if the user has since navigated
		// away or the doc has since been reloaded under a new name.
		if (window.cur_frm !== frm || frm.docname !== docname) return;
		if (g.has_workflow) return;

		// g.save_final_submit / revert_to_draft / cancel_delete are the
		// optional Permission Manager checkboxes (see
		// api/smart_action_permissions.py) — default true (no extra gate)
		// on any doctype where they haven't been provisioned, so this can
		// only ever narrow the base can_* rights below, never widen them.
		if (ds === 0 && g.can_submit && g.save_final_submit) {
			addSmartButton(
				frm,
				L("حفظ و إعتماد نهائي", "Save & Final Submit"),
				"submit",
				actSaveSubmit
			);
		}

		if (ds === 1) {
			if (g.can_cancel && g.can_delete && g.can_create && g.revert_to_draft) {
				addSmartButton(
					frm,
					L("الرجوع إلى المسودة", "Revert to Draft"),
					"revert",
					actRevertToDraft
				);
			}
			if (g.can_cancel && g.can_delete && g.cancel_delete) {
				addSmartButton(
					frm,
					L("إلغاء و حذف", "Cancel & Delete"),
					"delete",
					actCancelDelete
				);
			}
		}
	});
}

// ---- global form hook (patched ONCE) ---------------------------------------

function ensurePatched() {
	if (!window.frappe || !frappe.ui || !frappe.ui.form || !frappe.ui.form.Form) return;
	const proto = frappe.ui.form.Form.prototype;
	if (!proto || proto.__amtSmartActionsPatched) return;

	const origRefresh = proto.refresh;
	proto.refresh = function (...args) {
		const out = origRefresh.apply(this, args);
		// Defer so Frappe finishes building its own toolbar first.
		setTimeout(() => {
			try {
				decorate(this);
			} catch (e) {
				console.warn("[amt] smart-submit-actions", e);
			}
		}, 60);
		return out;
	};
	proto.__amtSmartActionsPatched = true;
}

export const smartSubmitActions = {
	mount() {
		if (window.frappe && frappe.ui && frappe.ui.form && frappe.ui.form.Form) {
			ensurePatched();
		} else {
			let tries = 0;
			const iv = setInterval(() => {
				tries++;
				if (window.frappe && frappe.ui && frappe.ui.form && frappe.ui.form.Form) {
					ensurePatched();
					clearInterval(iv);
				} else if (tries > 80) {
					clearInterval(iv);
				}
			}, 250);
		}
	},
};
