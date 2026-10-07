frappe.ui.form.on("Optical Prescription", {
    refresh(frm) {
        if (frm.is_new() || !frm.doc.previous_prescription) return;
        frm.add_custom_button(__("Compare with Previous"), () => {
            frappe.call({
                method: "optical.optical.doctype.optical_prescription.optical_prescription.compare_with_previous",
                args: { name: frm.doc.name },
            }).then((r) => {
                const d = r.message;
                if (!d) return;
                let html = `<table class="table table-bordered"><thead><tr>
                    <th></th><th colspan="2">${d.current} (${d.current_date})</th>
                    <th colspan="2">${d.previous} (${d.previous_date})</th></tr>
                    <tr><th></th><th>${__("OD")}</th><th>${__("OS")}</th><th>${__("OD")}</th><th>${__("OS")}</th></tr></thead><tbody>`;
                d.rows.forEach((x) => {
                    const changed = x.cur_od !== x.prev_od || x.cur_os !== x.prev_os;
                    html += `<tr ${changed ? 'style="background:#fff3cd"' : ""}><td><b>${x.label}</b></td>
                        <td>${x.cur_od}</td><td>${x.cur_os}</td><td>${x.prev_od}</td><td>${x.prev_os}</td></tr>`;
                });
                frappe.msgprint({ title: __("Prescription Comparison"), message: html + "</tbody></table>", wide: true });
            });
        });
    },
});
