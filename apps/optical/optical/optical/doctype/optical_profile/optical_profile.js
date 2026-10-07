frappe.ui.form.on("Optical Profile", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Eye Examination"), () => frappe.new_doc("Eye Examination", { customer: frm.doc.customer }), __("Create"));
        frm.add_custom_button(__("Optical Prescription"), () => frappe.new_doc("Optical Prescription", { customer: frm.doc.customer }), __("Create"));
        frm.add_custom_button(__("Optical Order"), () => frappe.new_doc("Optical Order", { customer: frm.doc.customer }), __("Create"));
    },
});
