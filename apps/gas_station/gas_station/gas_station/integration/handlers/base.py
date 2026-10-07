import frappe
from gas_station.gas_station.integration import normalize as n


class BaseHandler:
    """Each handler: persist raw history, update current state (fast),
    then enqueue expensive business processing."""
    operation = None

    def __init__(self, controller, data, raw_payload):
        self.controller = controller
        self.station = controller.station
        self.data = data or {}
        self.raw_payload = raw_payload

    # ---- to be implemented by subclasses ----
    def persist(self):
        raise NotImplementedError

    def update_state(self, doc):
        pass

    def enqueue_business(self, doc):
        pass

    # ---- shared helpers ----
    def _num(self, k):
        return n.num(self.data.get(k))

    def _s(self, k):
        return n.s(self.data.get(k))

    def _dt(self, k):
        return n.dt(self.data.get(k))
