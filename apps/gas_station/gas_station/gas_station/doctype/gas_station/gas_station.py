import frappe
from frappe.model.document import Document


class GasStation(Document):
    def validate(self):
        self._validate_company_currency()

    def _validate_company_currency(self):
        # Demo is designed around SAR; warn (don't block) if company differs.
        if not self.company:
            return
        currency = frappe.db.get_value("Company", self.company, "default_currency")
        if currency and currency != "SAR":
            frappe.msgprint(
                f"Company currency is {currency}. The Saudi demo data uses SAR.",
                indicator="orange", alert=True,
            )
