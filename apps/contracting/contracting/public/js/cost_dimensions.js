// Shared helper: show/hide construction cost dimensions per Construction Settings.
frappe.provide("contracting");

contracting._dims = null;
contracting.get_dims = function () {
	if (contracting._dims) return Promise.resolve(contracting._dims);
	return frappe.db.get_doc("Construction Settings").then(function (s) {
		contracting._dims = {
			ct_cost_code: !!s.enable_cost_code,
			ct_wbs: !!s.enable_wbs,
			ct_boq_item: !!s.enable_boq_item,
		};
		return contracting._dims;
	}).catch(function () {
		return { ct_cost_code: true, ct_wbs: true, ct_boq_item: true };
	});
};

contracting.toggle_cost_dims = function (frm, item_table) {
	contracting.get_dims().then(function (d) {
		Object.keys(d).forEach(function (fn) {
			var on = d[fn];
			if (frm.fields_dict[fn]) frm.toggle_display(fn, on);
			if (item_table && frm.fields_dict[item_table] && frm.fields_dict[item_table].grid) {
				frm.fields_dict[item_table].grid.update_docfield_property(fn, "hidden", on ? 0 : 1);
			}
		});
		if (item_table && frm.fields_dict[item_table] && frm.fields_dict[item_table].grid) {
			frm.fields_dict[item_table].grid.refresh();
		}
	});
};
