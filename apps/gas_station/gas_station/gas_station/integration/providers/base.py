"""Provider abstraction. Mock and Real both build the same normalized envelope
and feed the SAME dispatch.receive() pipeline (spec §42)."""
from abc import ABC, abstractmethod
from gas_station.gas_station.integration import dispatch


class PTSIntegrationProvider(ABC):
    @abstractmethod
    def to_envelope(self, operation: str, controller_code: str, data: dict) -> dict:
        ...

    def submit(self, operation, controller_code, data, raw_body=None, signature=None):
        envelope = self.to_envelope(operation, controller_code, data)
        return dispatch.receive(envelope, raw_body=raw_body, signature=signature)
