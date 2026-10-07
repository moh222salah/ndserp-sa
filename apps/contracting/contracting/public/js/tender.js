frappe.ui.form.on("Tender", {
	refresh: function (frm) {
		if (frm.is_new()) return;
		if (["Approved", "Awarded"].indexOf(frm.doc.status) === -1) return;
		frm.add_custom_button(__("Create Project Budget"), function () {
			frappe.prompt(
				[{ label: __("Awarded Project"), fieldname: "project", fieldtype: "Link", options: "Project", reqd: 1 }],
				function (v) {
					frm.call("create_budget_from_tender", { project: v.project }).then(function (r) {
						if (r.message) {
							frappe.show_alert({ message: __("Budget created"), indicator: "green" });
							frappe.set_route("Form", "Project Budget", r.message);
						}
					});
				}, __("Create Project Budget"), __("Create")
			);
		}, __("Actions"));
	},
});
