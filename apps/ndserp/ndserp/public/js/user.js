// Filter Role Profile picker for NDS module managers (Sales Manager, etc.).
frappe.ui.form.on("User", {
	onload(frm) {
		ndserp_apply_role_profile_filter(frm);
	},
	refresh(frm) {
		ndserp_apply_role_profile_filter(frm);
	},
});

function ndserp_apply_role_profile_filter(frm) {
	if (frappe.session.user === "Administrator") {
		return;
	}
	if (!(frappe.user && frappe.user.has_role && frappe.user.has_role("NDS Module Manager"))) {
		return;
	}
	// System Manager stays unrestricted even if they also hold the helper role.
	if (frappe.user.has_role("System Manager")) {
		return;
	}

	frappe.call({
		method: "ndserp.setup.user_provisioning.get_allowed_role_profiles_for_session",
		freeze: false,
		callback(r) {
			const allowed = r.message || [];
			const apply = () => {
				const filters = {
					filters: [["Role Profile", "name", "in", allowed.length ? allowed : ["__none__"]]],
				};
				// Table MultiSelect child Link field is `role_profile` under `role_profiles`.
				frm.set_query("role_profile", "role_profiles", () => filters);
				frm.set_query("role_profiles", () => filters);
				if (frm.fields_dict.role_profile_name) {
					frm.set_query("role_profile_name", () => filters);
				}
			};
			apply();
		},
	});
}
