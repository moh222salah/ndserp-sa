import frappe
from frappe.model.document import Document
from gas_station.gas_station.reconciliation import engine


class ReconciliationRun(Document):
    @frappe.whitelist()
    def run(self):
        self.set("results", [])
        rows = engine.run_reconciliation(
            self.recon_type, self.station, self.from_date, self.to_date
        )
        matched = exceptions = 0
        total_var = 0.0
        for r in rows:
            self.append("results", r)
            if r["status"] == "Matched":
                matched += 1
            else:
                exceptions += 1
            total_var += float(r.get("variance") or 0)
        self.matched_count = matched
        self.exception_count = exceptions
        self.total_variance = total_var
        self.run_at = frappe.utils.now_datetime()
        self.save()
        return {"matched": matched, "exceptions": exceptions}
