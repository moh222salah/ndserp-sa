frappe.ui.form.on("Optical Order", {
    setup(frm) {
        frm.set_query("prescription", () => ({ filters: { customer: frm.doc.customer } }));
        frm.set_query("warehouse", () => ({ filters: { company: frm.doc.company, is_group: 0 } }));
        frm.set_query("cost_center", () => ({ filters: { company: frm.doc.company, is_group: 0 } }));
        frm.set_query("insurance_plan", () => ({ filters: { is_active: 1 } }));
        frm.set_query("batch_no", "items", (doc, cdt, cdn) => ({ filters: { item: locals[cdt][cdn].item_code } }));
    },
    refresh(frm) {
        if (frm.is_new()) return;
        const run = (method) =>
            (frm.is_dirty() ? frm.save() : Promise.resolve())
                .then(() => frm.call(method))
                .then((r) => { frm.reload_doc(); return r; });
        const open_doc = (dt) => (r) => r.message && frappe.set_route("Form", dt, r.message);
        if (frm.doc.status === "Draft") {
            frm.add_custom_button(__("Confirm Order"), () => run("confirm_order")).addClass("btn-primary");
        }
        if (["Confirmed", "In Production", "Ready", "Delivered"].includes(frm.doc.status)) {
            if (!frm.doc.sales_invoice) {
                frm.add_custom_button(__("Customer Invoice"), () => run("make_sales_invoice").then(open_doc("Sales Invoice")), __("Create"));
            }
            if (frm.doc.insurance_amount > 0 && !frm.doc.insurer_invoice) {
                frm.add_custom_button(__("Insurer Invoice"), () => run("make_insurer_invoice").then(open_doc("Sales Invoice")), __("Create"));
            }
        }
        if (!["Delivered", "Cancelled"].includes(frm.doc.status) && frm.doc.status !== "Draft") {
            frm.add_custom_button(__("Cancel Order"), () => {
                frappe.confirm(__("Cancel this optical order?"), () => run("cancel_order"));
            }, __("Actions"));
        }
        if (frm.doc.optical_job) {
            frm.add_custom_button(__("Optical Job"), () => frappe.set_route("Form", "Optical Job", frm.doc.optical_job), __("View"));
        }
        if (frm.doc.sales_invoice) {
            frm.add_custom_button(__("Customer Invoice"), () => frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice), __("View"));
        }
    },
    customer(frm) {
        if (!frm.doc.customer) return;
        frappe.call({ method: "optical.api.get_profile_defaults", args: { customer: frm.doc.customer } }).then((r) => {
            const p = r.message || {};
            if (p.last_prescription && !frm.doc.prescription) frm.set_value("prescription", p.last_prescription);
            if (p.default_insurance_plan && !frm.doc.insurance_plan) frm.set_value("insurance_plan", p.default_insurance_plan);
        });
    },
    insurance_plan: (frm) => optical_calc(frm),
    discount_percent: (frm) => optical_calc(frm),
    discount_amount(frm) {
        if (frm.__calculating) return;
        frm.doc.discount_percent = 0;
        frm.refresh_field("discount_percent");
        optical_calc(frm);
    },
});

frappe.ui.form.on("Optical Order Item", {
    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code) return;
        frappe.call({ method: "optical.api.get_item_price", args: { item_code: row.item_code } }).then((r) => {
            const d = r.message || {};
            frappe.model.set_value(cdt, cdn, "rate", d.rate || 0);
            if (d.role && !row.item_role) frappe.model.set_value(cdt, cdn, "item_role", d.role);
        });
    },
    qty: (frm) => optical_calc(frm),
    rate: (frm) => optical_calc(frm),
    items_remove: (frm) => optical_calc(frm),
});

function optical_calc(frm) {
    frm.__calculating = true;
    let gross = 0;
    (frm.doc.items || []).forEach((r) => { r.amount = flt(r.qty) * flt(r.rate); gross += r.amount; });
    const discount = flt(frm.doc.discount_percent) ? (gross * flt(frm.doc.discount_percent)) / 100 : flt(frm.doc.discount_amount);
    frm.doc.gross_total = gross;
    frm.doc.discount_amount = discount;
    frm.doc.net_total = gross - discount;
    const finish = (insurer, customer) => {
        frm.doc.insurance_amount = insurer;
        frm.doc.customer_amount = customer;
        frm.refresh_fields();
        frm.__calculating = false;
    };
    if (frm.doc.insurance_plan) {
        frappe.call({ method: "optical.api.estimate_insurance", args: { net_total: frm.doc.net_total, plan: frm.doc.insurance_plan } })
            .then((r) => finish(r.message.insurer_amount, r.message.customer_amount));
    } else {
        finish(0, frm.doc.net_total);
    }
}
