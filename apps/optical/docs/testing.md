# Testing

Unit tests (no Frappe needed): `python -m unittest optical.tests.test_logic` from the app root.
Site tests to run manually (not yet automated): create customer -> exam -> prescription -> order with frame + 2 lenses
-> confirm -> invoice -> payment -> job through stages -> QC pass -> deliver; insurance approved order with insurer
invoice and settlement; QC fail -> remake; warranty claim; print every format in ar and en; role visibility per
Role Profile; multi-branch permissions.

## Known gaps / to verify on your bench
- Not run against a live ERPNext 16 site: DocType JSON, workspaces and number cards were generated to Frappe's format
  and may need small fixes on first `bench migrate` (send me the error output).
- Delayed Orders number card uses a dynamic filter; confirm it evaluates on your version.
- Single-screen POS, sales wizard, prescription OCR/AI, notifications (SMS/WhatsApp), customer 360 page, stocktaking
  and low/slow stock views (use ERPNext reports) are not built yet.
- Tax treatment of the insurer invoice depends on your tax template policy.
