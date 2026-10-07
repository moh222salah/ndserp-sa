frappe.ui.form.on("Optical Job", {
    setup(frm) {
        frm.set_query("laboratory", () => ({ filters: { is_active: 1 } }));
    },
    refresh(frm) {
        if (frm.is_new()) return;
        const run = (method, args) =>
            (frm.is_dirty() ? frm.save() : Promise.resolve())
                .then(() => frm.call(method, args))
                .then((r) => { frm.reload_doc(); return r; });
        if (!["Delivered", "Cancelled"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Next Stage"), () => run("advance_stage")).addClass("btn-primary");
        }
        if (frm.doc.lab_type === "External" && !frm.doc.purchase_order && frm.doc.status !== "Cancelled") {
            frm.add_custom_button(__("Purchase Order"), () =>
                run("make_purchase_order").then((r) => r.message && frappe.set_route("Form", "Purchase Order", r.message)), __("Create"));
        }
        if (frm.doc.status === "Quality Control") {
            frm.add_custom_button(__("Quality Control"), () => frappe.new_doc("Optical QC", { optical_job: frm.doc.name }), __("Create"));
        }
        frm.add_custom_button(__("Optical Order"), () => frappe.set_route("Form", "Optical Order", frm.doc.optical_order), __("View"));
    },
});
