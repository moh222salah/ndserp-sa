frappe.ui.form.on("Reconciliation Run", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Run Reconciliation"), () => {
			frm.call("run").then((r) => {
				const m = r.message || {};
				frappe.show_alert({
					message: __("Matched {0}, exceptions {1}", [m.matched, m.exceptions]),
					indicator: m.exceptions ? "orange" : "green",
				});
				frm.reload_doc();
			});
		}).addClass("btn-primary");
	},
});
