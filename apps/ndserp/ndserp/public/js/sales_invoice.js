// Sales Invoice: "Save" (button or Ctrl+S) runs the normal full cycle in one click:
// validate -> before_submit -> save -> submit -> on_submit, exactly like "Save & Submit",
// just without the extra "Permanently Submit?" confirmation.
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

	on_submit(frm) {
		// A paid value is settled by a Payment Entry created during submit: reload so status,
		// outstanding amount and the connections panel show the finished invoice.
		if (flt(frm.doc.nds_paid_amount)) frm.reload_doc();
	},

	nds_mode_of_payment(frm) {
		// Choosing a payment type with no amount yet proposes the full invoice total.
		if (frm.doc.nds_mode_of_payment && !frm.doc.nds_paid_amount) {
			const total = frm.doc.rounded_total || frm.doc.grand_total;
			if (total) frm.set_value("nds_paid_amount", total);
		}
	},

	nds_paid_amount(frm) {
		const paid = flt(frm.doc.nds_paid_amount);
		const total = flt(frm.doc.rounded_total || frm.doc.grand_total);
		if (paid && total && paid > total) {
			frappe.show_alert({ message: __("Paid value cannot exceed the invoice total."), indicator: "orange" });
			frm.set_value("nds_paid_amount", total);
		}
	},
});
