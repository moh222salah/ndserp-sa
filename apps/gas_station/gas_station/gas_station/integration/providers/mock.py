import time
from gas_station.gas_station.integration.providers.base import PTSIntegrationProvider


class MockPTSProvider(PTSIntegrationProvider):
    """Builds envelopes directly. Used by the simulator + demo seed."""
    def to_envelope(self, operation, controller_code, data):
        return {"controller": controller_code, "operation": operation,
                "packet_id": data.pop("packet_id", None) or f"MOCK-{int(time.time()*1000)}",
                "data": data}
