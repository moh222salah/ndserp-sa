from gas_station.gas_station.integration.providers.base import PTSIntegrationProvider


class RealPTSProvider(PTSIntegrationProvider):
    """Translates raw jsonPTS packets from a physical PTS-2 into the normalized
    envelope. Fill parse_raw() against your controller's exact jsonPTS shape;
    everything downstream (handlers, state, dashboard) is unchanged."""

    JSONPTS_TYPE_MAP = {
        "PumpTransaction": "UploadPumpTransaction",
        "TankMeasurement": "UploadTankMeasurement",
        "InTankDelivery": "UploadInTankDelivery",
        "AlertRecord": "UploadAlertRecord",
        "Status": "UploadStatus",
        "Configuration": "UploadConfiguration",
    }

    def to_envelope(self, operation, controller_code, data):
        return {"controller": controller_code, "operation": operation, "data": data}

    def parse_raw(self, raw_packet: dict) -> dict:
        """Map a real jsonPTS packet -> normalized envelope.
        Adjust field paths to match your PTS-2 firmware/protocol version."""
        packet = raw_packet.get("Packet", raw_packet)
        controller_code = packet.get("Id") or packet.get("ConfigurationId")
        pts_type = packet.get("Type")
        operation = self.JSONPTS_TYPE_MAP.get(pts_type, pts_type)
        data = packet.get("Data") or {}
        return {"controller": controller_code, "operation": operation,
                "packet_id": packet.get("PacketId"), "data": data}
