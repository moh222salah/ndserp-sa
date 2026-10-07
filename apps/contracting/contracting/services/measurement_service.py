"""Operation Measurement value (simplified, Project + Budget BOQ Item).

Construction quantities are numeric; unit is free text. Certified value =
measured qty x unit price. Previous/Total come from prior approved measurements.
"""
import frappe


def item_value(qty, unit_price):
	return (qty or 0) * (unit_price or 0)


def get_previous(boq_item, exclude_measurement):
	if not boq_item:
		return 0.0, 0.0
	row = frappe.db.sql("""
		select coalesce(sum(omi.qty),0), coalesce(sum(omi.current_value),0)
		from `tabOperation Measurement Item` omi
		inner join `tabOperation Measurement` om on omi.parent=om.name
		where omi.boq_item=%s and om.status='Approved' and om.name!=%s
	""", (boq_item, exclude_measurement or ""))[0]
	return float(row[0] or 0), float(row[1] or 0)
