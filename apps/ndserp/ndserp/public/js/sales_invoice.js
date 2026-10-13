// Sales Invoice: "Save" (button or Ctrl+S) runs the normal full cycle in one click:
// validate -> before_submit -> save -> submit -> on_submit, exactly like "Save & Submit",
// just without the extra "Permanently Submit?" confirmation.
// Also: entering the paid value updates paid / outstanding amounts live, before saving.

function nds_apply_paid(frm) {
if (frm.doc.docstatus !== 0) return;
const total = flt(frm.doc.rounded_total || frm.doc.grand_total);
const paid = Math.min(flt(frm.doc.nds_paid_amount), total);
const outstanding = Math.max(total - flt(frm.doc.total_advance) - paid, 0);
frm.doc.paid_amount = paid;
frm.doc.base_paid_amount = flt(paid * flt(frm.doc.conversion_rate || 1));
frm.doc.outstanding_amount = outstanding;
frm.refresh_fields(["paid_amount", "base_paid_amount", "outstanding_amount"]);
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
// savesubmit() asks "Permanently Submit?" through frappe.confirm: answer it for the user, once.
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
// Re-run the live calculation whenever ERPNext recalculates the totals.
if (!frm.__nds_totals_hooked && frm.cscript && frm.cscript.calculate_taxes_and_totals) {
frm.__nds_totals_hooked = true;
const original_calc = frm.cscript.calculate_taxes_and_totals;
frm.cscript.calculate_taxes_and_totals = function () {
const result = original_calc.apply(this, arguments);
Promise.resolve(result).then(() => nds_apply_paid(frm));
return result;
};
}
nds_apply_paid(frm);
},

on_submit(frm) {
// A paid value is settled by a Payment Entry created during submit: reload so status,
// outstanding amount and the connections panel show the finished invoice.
if (flt(frm.doc.nds_paid_amount)) frm.reload_doc();
},

grand_total(frm) { nds_apply_paid(frm); },
rounded_total(frm) { nds_apply_paid(frm); },
total_advance(frm) { nds_apply_paid(frm); },
items_add(frm) { setTimeout(() => nds_apply_paid(frm), 300); },
items_remove(frm) { setTimeout(() => nds_apply_paid(frm), 300); },

nds_mode_of_payment(frm) {
// Choosing a payment type with no amount yet proposes the full invoice total.
if (frm.doc.nds_mode_of_payment && !frm.doc.nds_paid_amount) {
const total = frm.doc.rounded_total || frm.doc.grand_total;
if (total) frm.set_value("nds_paid_amount", total);
}
nds_apply_paid(frm);
},

nds_paid_amount(frm) {
const paid = flt(frm.doc.nds_paid_amount);
const total = flt(frm.doc.rounded_total || frm.doc.grand_total);
if (paid && total && paid > total) {
frappe.show_alert({ message: __("Paid value cannot exceed the invoice total."), indicator: "orange" });
frm.set_value("nds_paid_amount", total);
}
nds_apply_paid(frm);
},
});
