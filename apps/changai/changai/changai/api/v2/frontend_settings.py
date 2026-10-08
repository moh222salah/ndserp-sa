"""Lightweight frontend settings endpoint for ChangAI.

This module intentionally imports only Frappe so the desk chatbot settings
request cannot fail because optional AI/ML dependencies are absent.
"""

import frappe

CHANGAI_SETTINGS = "ChangAI Settings"


@frappe.whitelist(allow_guest=False)
def get_frontend_settings():
    """Return safe, non-secret ChangAI settings required by the desk UI."""
    aws_access_key_id = (
        frappe.db.get_single_value(CHANGAI_SETTINGS, "aws_access_key_id") or ""
    ).strip()
    aws_secret_access_key = (
        frappe.db.get_single_value(CHANGAI_SETTINGS, "aws_secret_access_key") or ""
    ).strip()
    aws_region = (
        frappe.db.get_single_value(CHANGAI_SETTINGS, "aws_region")
        or frappe.db.get_single_value(CHANGAI_SETTINGS, "aws_default_region")
        or "us-east-1"
    )
    enable_voice_chat = bool(
        frappe.db.get_single_value(CHANGAI_SETTINGS, "enable_voice_chat")
    )
    enable_changai = bool(
        frappe.db.get_single_value(CHANGAI_SETTINGS, "enable_changai")
    )
    to_language = (
        frappe.db.get_single_value(CHANGAI_SETTINGS, "to_language") or ""
    )

    return {
        "enable_voice_chat": enable_voice_chat,
        "aws_region": aws_region,
        "polly_voice_id": "Zayd",
        "polly_enabled": bool(
            enable_voice_chat and aws_access_key_id and aws_secret_access_key
        ),
        "enable_changai": enable_changai,
        "to_language": to_language,
    }
