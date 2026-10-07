from frappe.model.document import Document


class ContractClaim(Document):
    def validate(self):
        # Claims affect the Final Account, not the BOQ baseline.
        self.claimed_amount = sum((r.claimed_amount or 0) for r in self.items) or self.claimed_amount
        self.assessed_amount = sum((r.assessed_amount or 0) for r in self.items) or self.assessed_amount
        self.approved_amount = sum((r.approved_amount or 0) for r in self.items) or self.approved_amount
