"""Controller identification + credential/HMAC verification."""
import hashlib
import hmac
import frappe


class UnknownController(frappe.ValidationError):
    pass


class AuthError(frappe.ValidationError):
    pass


def identify_controller(envelope: dict):
    code = envelope.get("controller") or envelope.get("configuration_id")
    if not code:
        raise UnknownController("No controller identifier in packet.")
    name = frappe.db.get_value("PTS Controller", {"controller_code": code}) \
        or frappe.db.get_value("PTS Controller", {"configuration_id": code})
    if not name:
        raise UnknownController(f"Unknown controller: {code}")
    return frappe.get_doc("PTS Controller", name)


def verify(controller, raw_body: str = None, signature: str = None):
    """If the controller has an HMAC secret, require a valid signature.
    Real PTS-2 signature scheme is configured per-controller; adjust here."""
    secret = controller.get_password("hmac_secret", raise_exception=False) \
        if controller.hmac_secret else None
    if not secret:
        return True
    if not signature or raw_body is None:
        raise AuthError("Missing signature for a controller that requires HMAC.")
    expected = hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthError("Invalid HMAC signature.")
    return True
