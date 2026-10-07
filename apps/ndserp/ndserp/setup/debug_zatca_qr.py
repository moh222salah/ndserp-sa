"""Debug ZATCA Phase 1 QR payload and PNG."""

from __future__ import annotations

import base64

from ksa_compliance.jinja import _generate_decoded_string, _get_qr_inputs, get_zatca_phase_1_qr_for_invoice


def run(invoice: str = "ACC-SINV-2026-00161"):
	values = _get_qr_inputs(invoice)
	tlv_b64 = _generate_decoded_string(values) if values else None
	raw = base64.b64decode(tlv_b64) if tlv_b64 else b""
	tags = []
	i = 0
	while i < len(raw):
		tag = raw[i]
		i += 1
		length = raw[i]
		i += 1
		val = raw[i : i + length]
		i += length
		tags.append({"tag": tag, "len": length, "val": val.decode("utf-8", errors="replace")})

	qr_b64 = get_zatca_phase_1_qr_for_invoice(invoice)
	png = base64.b64decode(qr_b64) if qr_b64 else b""
	path = f"/tmp/zatca_qr_{invoice.replace('/', '_')}.png"
	if png:
		with open(path, "wb") as f:
			f.write(png)

	return {
		"values": [str(v) for v in values] if values else None,
		"tags": tags,
		"png_bytes": len(png),
		"png_path": path,
	}
