// Sales Invoice: "Save" saves AND submits in one click (no separate "Submit" step).
frappe.ui.form.on("Sales Invoice", {
	setup(frm) {
		if (frm.__nds_one_click_save) return;
		frm.__nds_one_click_save = true;

		const original_save = frm.save.bind(frm);
		frm.save = function (save_action, callback, btn, on_error) {
			// Only plain saves of a draft are promoted; Submit / Update / Cancel are untouched.
			const plain_save = !save_action || save_action === "Save";
			if (plain_save && frm.doc.docstatus === 0 && !frm.__nds_saving) {
				frm.__nds_saving = true;
				const done = () => { frm.__nds_saving = false; };
				return original_save(
					"Submit",
					(r) => { done(); if (callback) callback(r); },
					btn,
					(r) => { done(); if (on_error) on_error(r); }
				);
			}
			return original_save(save_action, callback, btn, on_error);
		};
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
