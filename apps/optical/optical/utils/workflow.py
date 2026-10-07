"""Optical Job stage logic (pure)."""

STAGES = [
    "New",
    "Prescription Verification",
    "Measurements Confirmed",
    "Preparation",
    "Laboratory",
    "Assembly",
    "Quality Control",
    "Ready",
    "Notified",
    "Delivered",
]

# stage -> Optical Settings checkbox controlling it. Stages not listed are always on.
STAGE_FLAGS = {
    "Prescription Verification": "enable_rx_verification",
    "Measurements Confirmed": "enable_measurements_confirmation",
    "Preparation": "enable_preparation",
    "Laboratory": "enable_laboratory",
    "Assembly": "enable_assembly",
    "Quality Control": "enable_quality_control",
    "Notified": "enable_customer_notification",
}


def enabled_stages(flags):
    """flags: mapping of settings fieldname -> truthy/falsy."""
    return [s for s in STAGES if s not in STAGE_FLAGS or flags.get(STAGE_FLAGS[s])]


def next_stage(current, flags):
    stages = enabled_stages(flags)
    if current not in STAGES:
        return None
    idx = STAGES.index(current)
    for s in STAGES[idx + 1:]:
        if s in stages:
            return s
    return None
