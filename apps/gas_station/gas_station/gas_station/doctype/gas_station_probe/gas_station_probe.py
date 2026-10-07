from frappe.model.document import Document


class GasStationProbe(Document):
    def available_measurements(self):
        """Return the set of measurement fields this probe actually provides.
        The dashboard uses this so unavailable readings render as '—', not 0."""
        caps = {
            "product_level": self.supports_level,
            "water_level": self.supports_water,
            "temperature": self.supports_temperature,
            "density": self.supports_density,
            "leak": self.supports_leak,
        }
        return {k for k, v in caps.items() if v}
