"""Login-safe ChangAI session initialization.

ChangAI's original session hook performs heavyweight imports, schema loading, and
model/vector-store warmup inside Frappe's session-creation path. During a normal
password login that work runs before the /api/method/login request can return.

Keep the existing warmup behavior for ordinary session creation, but never let
it execute synchronously inside the authentication request.
"""

from __future__ import annotations

import frappe

_LOGIN_PATHS = {
    "/api/method/login",
    "/login",
    "/login/",
}


def on_session_creation() -> None:
    """Run ChangAI session warmup only when it cannot block authentication."""
    request = getattr(frappe.local, "request", None)
    path = getattr(request, "path", "") or ""

    if path in _LOGIN_PATHS or frappe.local.form_dict.get("cmd") == "login":
        return

    for method in (
        "changai.changai.api.v2.retrieve.load_on_startup",
        "changai.changai.api.v2.schema_utils.reload_mapping_schema_cache",
    ):
        try:
            frappe.call(method)
        except Exception:
            frappe.log_error(
                title="ChangAI session startup hook failed",
                message=frappe.get_traceback(),
            )
