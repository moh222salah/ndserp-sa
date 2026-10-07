frappe.ui.form.on("Customer", {
    refresh(frm) {
        if (frm.is_new()) return;
        const group = __("Optical");
        frm.add_custom_button(__("Optical Profile"), () => {
            frappe.call({ method: "optical.api.open_profile", args: { customer: frm.doc.name } })
                .then((r) => frappe.set_route("Form", "Optical Profile", r.message));
        }, group);
        frm.add_custom_button(__("New Eye Examination"), () => {
            frappe.new_doc("Eye Examination", { customer: frm.doc.name });
        }, group);
        frm.add_custom_button(__("New Optical Order"), () => {
            frappe.new_doc("Optical Order", { customer: frm.doc.name });
        }, group);
    },
});
