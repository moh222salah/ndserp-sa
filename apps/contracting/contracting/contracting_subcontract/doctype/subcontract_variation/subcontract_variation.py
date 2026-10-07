import frappe
from frappe.model.document import Document
from contracting.services.subcontract_engine import recompute_subcontract


class SubcontractVariation(Document):
    def validate(self):
        total = 0.0
        for row in self.items:
            if row.change_type == "Rate Change" and row.subcontract_boq_item:
                q, r = frappe.db.get_value("Subcontract BOQ Item", row.subcontract_boq_item,
                    ["qty", "rate"]) or (0, 0)
                row.variation_amount = ((row.variation_rate or 0) - (r or 0)) * (q or 0)
            else:
                eff_rate = row.variation_rate or 0
                if not eff_rate and row.subcontract_boq_item:
                    eff_rate = frappe.db.get_value("Subcontract BOQ Item",
                        row.subcontract_boq_item, "rate") or 0
                row.variation_amount = (row.variation_qty or 0) * eff_rate
            total += row.variation_amount or 0
        self.variation_value = total

    def on_update(self):
        recompute_subcontract(self.subcontract)

    def on_cancel(self):
        recompute_subcontract(self.subcontract)

    def on_trash(self):
        recompute_subcontract(self.subcontract)
