import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class CSICode(NestedSet):
    nsm_parent_field = "parent_csi_code"

    def validate(self):
        if self.parent_csi_code == self.name:
            frappe.throw(_("CSI Code cannot be its own parent."))
