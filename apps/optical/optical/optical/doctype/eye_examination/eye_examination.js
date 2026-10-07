frappe.ui.form.on("Eye Examination", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.prescription) return;
        frm.add_custom_button(__("Optical Prescription"), () => {
            frappe.model.open_mapped_doc({
                method: "optical.optical.doctype.eye_examination.eye_examination.make_prescription",
                frm: frm,
            });
        }, __("Create"));
    },
});
