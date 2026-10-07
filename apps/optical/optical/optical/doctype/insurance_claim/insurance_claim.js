frappe.ui.form.on("Insurance Claim", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.status === "Approved" && !frm.doc.insurer_invoice) {
            frm.add_custom_button(__("Insurer Invoice"), () => {
                (frm.is_dirty() ? frm.save() : Promise.resolve())
                    .then(() => frm.call("make_insurer_invoice"))
                    .then((r) => r.message && frappe.set_route("Form", "Sales Invoice", r.message));
            }, __("Create"));
        }
    },
});
