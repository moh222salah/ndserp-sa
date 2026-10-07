import frappe, base64
from ndserp.jinja import get_ndserp_zatca_phase_1_qr, _get_phase_1_qr_values
from ksa_compliance.jinja import _generate_decoded_string
inv='ACC-SINV-2026-00161'
vals=_get_phase_1_qr_values(inv)
print('VALS', vals)
raw=base64.b64decode(_generate_decoded_string(vals))
i=0
while i<len(raw):
    tag=raw[i]; i+=1; ln=raw[i]; i+=1; val=raw[i:i+ln]; i+=ln
    print(tag, val)
png=base64.b64decode(get_ndserp_zatca_phase_1_qr(inv))
open('/tmp/zatca_qr_fixed.png','wb').write(png)
import struct
print('PNG', struct.unpack('>II', png[16:24]), 'bytes', len(png))
# render print
from frappe.www.printview import get_rendered_template
from frappe.utils.pdf import get_pdf
frappe.set_user('Administrator')
doc=frappe.get_doc('Sales Invoice', inv)
pf=frappe.get_doc('Print Format','ZATCA Tax Invoice')
html=get_rendered_template(doc=doc, print_format=pf, no_letterhead=1)
print('uses_ndserp_helper', 'get_ndserp_zatca_phase_1_qr' not in html)  # helper resolved
print('has_200', 'width="200"' in html or '200px' in html)
print('has_qr', 'data:image/png;base64,' in html and 'data:image/png;base64, {{' not in html)
print('pdf', len(get_pdf(html)))
