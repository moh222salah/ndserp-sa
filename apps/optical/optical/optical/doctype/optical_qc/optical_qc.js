frappe.ui.form.on("Optical QC", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.result === "Fail" && !frm.doc.remake) {
            frm.add_custom_button(__("Optical Remake"), () => {
                (frm.is_dirty() ? frm.save() : Promise.resolve())
                    .then(() => frm.call("make_remake"))
                    .then((r) => r.message && frappe.set_route("Form", "Optical Remake", r.message));
            }, __("Create"));
        }
    },
});
