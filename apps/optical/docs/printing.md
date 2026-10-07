# Printing

Standard Jinja print formats shipped in `optical/optical/print_format`: Optical Lab Sheet (Optical Job),
Optical Prescription Print, Optical Delivery Receipt (Optical Order), Optical Warranty Certificate,
Optical Remake Form, Optical Tax Invoice A4 and Optical POS Receipt 80mm (Sales Invoice).
Templates call helpers from `optical/utils/printing.py` (registered in hooks `jinja`) for direction and optical data.
Direction follows the print language. For the 80mm receipt also set the paper size in your browser/printer
profile (wkhtmltopdf ignores CSS @page). ZATCA / e-invoicing QR are out of scope for now.
