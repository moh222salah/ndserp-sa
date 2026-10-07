# Translations

Arabic ships as `optical/locale/ar.po` (gettext) and `optical/translations/ar.csv`.
Verify which mechanism your Frappe 16 install loads (look for `.po` under `apps/frappe/frappe/locale`), keep that one
and delete the other. All user strings use `_()` / `__()` or DocType labels; nothing is hard-coded in templates.
Glossary: Customer العميل, Optical Profile الملف البصري, Eye Examination فحص النظر, Prescription وصفة النظر,
Frame الإطار, Lens العدسة, Contact Lens العدسات اللاصقة, Coating معالجة العدسة, Optical Order طلب النظارة,
Optical Job أمر تجهيز النظارة, Laboratory المعمل, Quality Control فحص الجودة, Remake إعادة التصنيع,
Warranty الضمان, Insurance التأمين, Branch الفرع.
After adding strings: `bench generate-pot-file --app optical` then `bench update-po-files --app optical --locale ar`.
Where a word needs context (e.g. Charge), add a `msgctxt` via `_("Charge", context="Optical Fee")`.
