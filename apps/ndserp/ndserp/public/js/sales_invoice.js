// Sales Invoice: one-click "Save" runs the full Save & Submit cycle (no confirm dialog).
// Paid value: auto-filled with the invoice total as items are entered (until the user edits it),
// and paid / outstanding amounts update live, before saving.

function nds_total(frm) {
    return flt(frm.doc.rounded_total || frm.doc.grand_total);
}

function nds_apply_paid(frm) {
    if (frm.doc.docstatus !== 0) return;
    const total = nds_total(frm);
    const paid = Math.min(flt(frm.doc.nds_paid_amount), total);
    frm.doc.paid_amount = paid;
    frm.doc.base_paid_amount = flt(paid * flt(frm.doc.conversion_rate || 1));
    frm.doc.outstanding_amount = Math.max(total - flt(frm.doc.total_advance) - paid, 0);
    frm.refresh_fields(["paid_amount", "base_paid_amount", "outstanding_amount"]);
}

function nds_sync_paid(frm) {
    if (frm.doc.docstatus !== 0) return;
    const total = nds_total(frm);
    if (!frm.__nds_paid_manual && frm.doc.nds_mode_of_payment && total
        && flt(frm.doc.nds_paid_amount) !== total) {
        frm.__nds_auto = true;
        Promise.resolve(frm.set_value("nds_paid_amount", total))
            .finally(() => { frm.__nds_auto = false; nds_apply_paid(frm); });
        return;
    }
    nds_apply_paid(frm);
}

function nds_later(frm) {
    clearTimeout(frm.__nds_timer);
    frm.__nds_timer = setTimeout(() => nds_sync_paid(frm), 400);
}

frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        if (frm.__nds_one_click_save) return;
        frm.__nds_one_click_save = true;

        const original_save = frm.save.bind(frm);
        frm.save = function (save_action, callback, btn, on_error) {
            const plain_save = !save_action || save_action === "Save";
            if (!plain_save || frm.doc.docstatus !== 0 || frm.__nds_saving) {
                return original_save(save_action, callback, btn, on_error);
            }

            frm.__nds_saving = true;
            const finish = () => { frm.__nds_saving = false; };
            const confirm_original = frappe.confirm;
            frappe.confirm = function (message, if_yes) {
                frappe.confirm = confirm_original;
                if (typeof if_yes === "function") if_yes();
            };
            try {
                return Promise.resolve(
                    frm.savesubmit(
                        btn,
                        (r) => { finish(); if (callback) callback(r); },
                        (r) => { finish(); if (on_error) on_error(r); }
                    )
                ).catch(() => { finish(); }).finally(() => {
                    finish();
                    frappe.confirm = confirm_original;
                });
            } catch (e) {
                finish();
                frappe.confirm = confirm_original;
                throw e;
            }
        };
    },

    refresh(frm) {
        if (!frm.__nds_totals_hooked && frm.cscript && frm.cscript.calculate_taxes_and_totals) {
            frm.__nds_totals_hooked = true;
            const original_calc = frm.cscript.calculate_taxes_and_totals;
            frm.cscript.calculate_taxes_and_totals = function () {
                const result = original_calc.apply(this, arguments);
                Promise.resolve(result).then(() => nds_sync_paid(frm));
                return result;
            };
        }
        nds_sync_paid(frm);
    },

    on_submit(frm) {
        if (flt(frm.doc.nds_paid_amount)) frm.reload_doc();
    },

    grand_total(frm) { nds_later(frm); },
    rounded_total(frm) { nds_later(frm); },
    total_advance(frm) { nds_later(frm); },
    items_add(frm) { nds_later(frm); },
    items_remove(frm) { nds_later(frm); },

    nds_mode_of_payment(frm) {
        nds_sync_paid(frm);
    },

    nds_paid_amount(frm) {
        if (!frm.__nds_auto) frm.__nds_paid_manual = true;
        const paid = flt(frm.doc.nds_paid_amount);
        const total = nds_total(frm);
        if (paid && total && paid > total) {
            frappe.show_alert({ message: __("Paid value cannot exceed the invoice total."), indicator: "orange" });
            frm.__nds_auto = true;
            Promise.resolve(frm.set_value("nds_paid_amount", total))
                .finally(() => { frm.__nds_auto = false; });
        }
        nds_apply_paid(frm);
    },
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm) { nds_later(frm); },
    qty(frm) { nds_later(frm); },
    rate(frm) { nds_later(frm); },
    amount(frm) { nds_later(frm); },
});
