from frappe.model.document import Document


class ProcurementPlan(Document):
    def validate(self):
        # Ordered/Received/Issued are fed by ERPNext Buying/Stock adapters in a later phase;
        # here we keep the derived remaining balance consistent.
        for row in self.items:
            base = row.planned_qty or row.required_qty or 0
            row.remaining_qty = base - (row.received_qty or 0)
