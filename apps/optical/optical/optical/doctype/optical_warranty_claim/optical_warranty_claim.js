frappe.ui.form.on("Optical Warranty Claim", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.claim_type === "Remake" && frm.doc.status === "Approved" && !frm.doc.remake) {
            frm.add_custom_button(__("Optical Remake"), () => {
                (frm.is_dirty() ? frm.save() : Promise.resolve())
                    .then(() => frm.call("make_remake"))
                    .then((r) => r.message && frappe.set_route("Form", "Optical Remake", r.message));
            }, __("Create"));
        }
    },
});
