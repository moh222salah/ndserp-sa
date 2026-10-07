# Copyright (c) 2026, NDS and contributors
# License: MIT

from frappe.model.document import Document


class NDSOrderCounter(Document):
	"""P7-T2: last daily order number per POS Profile and day (1900-01-01 = never reset)."""

	pass
