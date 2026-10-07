frappe.ui.form.on("Optical Remake", {
    setup(frm) {
        frm.set_query("laboratory", () => ({ filters: { is_active: 1 } }));
    },
});
