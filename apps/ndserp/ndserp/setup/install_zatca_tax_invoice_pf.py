"""Install / update the ZATCA Tax Invoice print format (inv.pdf layout)."""

from __future__ import annotations

import frappe

PRINT_FORMAT_NAME = "ZATCA Tax Invoice"

HTML = r"""
<style>
@page { size: A4; margin: 10mm; }
.zatca-inv { font-family: Tahoma, Arial, sans-serif; font-size: 11px; color: #111; direction: rtl; }
.zatca-inv * { box-sizing: border-box; }
.zatca-inv .hdr { width: 100%; display: table; margin-bottom: 10px; border-bottom: 2px solid #222; padding-bottom: 8px; }
.zatca-inv .hdr-right, .zatca-inv .hdr-left { display: table-cell; vertical-align: middle; }
.zatca-inv .hdr-right { width: 70%; text-align: right; }
.zatca-inv .hdr-left { width: 30%; text-align: center; }
.zatca-inv .title-ar { font-size: 22px; font-weight: 700; margin: 0; }
.zatca-inv .title-en { font-size: 14px; color: #444; margin: 2px 0 0; direction: ltr; text-align: right; }
.zatca-inv .qr { text-align: center; }
.zatca-inv .qr img {
  width: 200px;
  height: 200px;
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  image-rendering: pixelated;
  -ms-interpolation-mode: nearest-neighbor;
}
.zatca-inv .meta-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
.zatca-inv .meta-table td { vertical-align: top; padding: 0; }
.zatca-inv .box { border: 1px solid #333; padding: 8px 10px; min-height: 110px; }
.zatca-inv .box-title { font-weight: 700; font-size: 12px; margin-bottom: 6px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
.zatca-inv .row-line { margin: 3px 0; line-height: 1.45; }
.zatca-inv .lbl { color: #555; }
.zatca-inv .val { font-weight: 600; }
.zatca-inv .en { direction: ltr; unicode-bidi: embed; }
.zatca-inv .items { width: 100%; border-collapse: collapse; margin: 10px 0; }
.zatca-inv .items th, .zatca-inv .items td { border: 1px solid #333; padding: 5px 4px; text-align: center; vertical-align: middle; }
.zatca-inv .items th { background: #f3f3f3; font-size: 10px; }
.zatca-inv .items td.desc { text-align: right; }
.zatca-inv .totals-wrap { width: 100%; display: table; margin-top: 8px; }
.zatca-inv .totals-left, .zatca-inv .totals-right { display: table-cell; vertical-align: top; }
.zatca-inv .totals-left { width: 50%; text-align: right; padding-left: 10px; }
.zatca-inv .totals-right { width: 50%; }
.zatca-inv .totals { width: 100%; border-collapse: collapse; }
.zatca-inv .totals td { border: 1px solid #333; padding: 5px 8px; }
.zatca-inv .totals td.k { text-align: right; background: #f7f7f7; width: 65%; }
.zatca-inv .totals td.v { text-align: left; direction: ltr; font-weight: 700; width: 35%; }
.zatca-inv .words-box {
  width: 100%;
  border: 1px solid #333;
  padding: 8px 10px;
  margin-top: 10px;
  background: #fafafa;
  font-size: 12px;
  line-height: 1.6;
}
.zatca-inv .words-box .words-label { color: #555; font-weight: 700; margin-bottom: 4px; }
.zatca-inv .words-box .words-value { font-weight: 700; font-size: 13px; }
.zatca-inv .err { color: #b91c1c; font-size: 14px; font-weight: 700; text-align: center; padding: 20px; }
.zatca-inv .gap { width: 8px; }
</style>

{% set phase1 = frappe.db.get_value("ZATCA Phase 1 Business Settings", {"company": doc.company}, ["company","vat_registration_number","address","status","type_of_transaction"], as_dict=True) %}
{% if not phase1 or phase1.status != "Active" %}
<div class="zatca-inv">
  <p class="err">{{ doc.company }} : {{ _("Does not have active ZATCA Phase 1 Business Settings") }}</p>
</div>
{% else %}
{% set street, city, district, postal_code = frappe.db.get_value("Address", phase1.address, ["address_line1","city","state","pincode"]) or (None, None, None, None) %}
{% set zatca_bs = frappe.db.get_value("ZATCA Business Settings", {"company": doc.company}, "name") %}
{% set seller_crn = None %}
{% if zatca_bs %}
  {% set seller_crn = frappe.db.get_value("Additional Seller IDs", {"parent": zatca_bs, "type_code": "CRN"}, "value") %}
{% endif %}
{% set customer_vat = doc.tax_id %}
{% if not customer_vat and doc.customer %}
  {% set customer_vat = frappe.db.get_value("Customer", doc.customer, "tax_id") %}
{% endif %}
{% set customer_crn = frappe.db.get_value("Additional Buyer IDs", {"parent": doc.customer, "type_name": "Commercial Registration Number"}, "value") %}
{% if not customer_crn %}
  {% set customer_crn = frappe.db.get_value("Additional Buyer IDs", {"parent": doc.customer, "type_code": "CRN"}, "value") %}
{% endif %}
{% set buyer_address_name = frappe.db.get_value("Dynamic Link", {"parenttype": "Address", "link_doctype": "Customer", "link_name": doc.customer}, "parent") %}
{% set buyer_street, buyer_city, buyer_district, buyer_postal = (None, None, None, None) %}
{% if buyer_address_name %}
  {% set buyer_street, buyer_city, buyer_district, buyer_postal = frappe.db.get_value("Address", buyer_address_name, ["address_line1","city","state","pincode"]) or (None, None, None, None) %}
{% endif %}
{% set supply_date = doc.get("delivery_date") or doc.posting_date %}
{% set customer_group = doc.customer_group %}
{% if not customer_group and doc.customer %}
  {% set customer_group = frappe.db.get_value("Customer", doc.customer, "customer_group") %}
{% endif %}
{% if customer_group == "Individual" %}
  {% set invoice_type = "Simplified" %}
{% else %}
  {% set invoice_type = "Standard" %}
{% endif %}

{% if doc.is_return %}
  {% set title_ar = "إشعار دائن ضريبي" if invoice_type == "Standard" else "إشعار دائن ضريبي مبسط" %}
  {% set title_en = "Tax Invoice Credit Note" if invoice_type == "Standard" else "Simplified Tax Invoice Credit Note" %}
{% elif doc.is_debit_note %}
  {% set title_ar = "إشعار مدين ضريبي" if invoice_type == "Standard" else "إشعار مدين ضريبي مبسط" %}
  {% set title_en = "Tax Invoice Debit Note" if invoice_type == "Standard" else "Simplified Tax Invoice Debit Note" %}
{% else %}
  {% set title_ar = "فاتورة ضريبية" if invoice_type == "Standard" else "فاتورة ضريبية مبسطة" %}
  {% set title_en = "Tax Invoice" if invoice_type == "Standard" else "Simplified Tax Invoice" %}
{% endif %}

<div class="zatca-inv">
  <div class="hdr">
    <div class="hdr-right">
      <p class="title-ar">{{ title_ar }}</p>
      <p class="title-en">{{ title_en }}</p>
    </div>
    <div class="hdr-left qr">
      {% set qr = get_ndserp_zatca_phase_1_qr(doc.name) %}
      {% if qr %}
      <img src="data:image/png;base64,{{ qr }}" width="200" height="200" alt="ZATCA QR">
      {% endif %}
    </div>
  </div>

  <table class="meta-table">
    <tr>
      <td style="width:48%">
        <div class="box">
          <div class="box-title">Buyer / العميل</div>
          <div class="row-line"><span class="lbl">الاسم / Name :</span> <span class="val">{{ doc.customer_name or doc.customer }}</span></div>
          <div class="row-line"><span class="lbl">العنوان / Address :</span>
            <span class="val">
              {% if buyer_street %}{{ buyer_street }}{% endif %}
              {% if buyer_district %}{% if buyer_street %} - {% endif %}{{ buyer_district }}{% endif %}
              {% if buyer_city %}{% if buyer_street or buyer_district %} - {% endif %}{{ buyer_city }}{% endif %}
              {% if buyer_postal %} | {{ buyer_postal }}{% endif %}
            </span>
          </div>
          <div class="row-line"><span class="lbl">سجل تجاري / CRN :</span> <span class="val en">{{ customer_crn or "" }}</span></div>
          <div class="row-line"><span class="lbl">الرقم الضريبي / VAT NO. :</span> <span class="val en">{{ customer_vat or "" }}</span></div>
        </div>
      </td>
      <td class="gap"></td>
      <td style="width:48%">
        <div class="box">
          <div class="box-title">Invoice Details / بيانات الفاتورة</div>
          <div class="row-line"><span class="lbl">رقم الفاتورة / Invoice Number :</span> <span class="val en">{{ doc.name }}</span></div>
          <div class="row-line"><span class="lbl">تاريخ الفاتورة / Invoice Date :</span> <span class="val en">{{ frappe.utils.formatdate(doc.posting_date, "yyyy/MM/dd") }}</span></div>
          <div class="row-line"><span class="lbl">تاريخ التوريد / Supply Date :</span> <span class="val en">{{ frappe.utils.formatdate(supply_date, "dd/MM/yyyy") }}</span></div>
        </div>
      </td>
    </tr>
  </table>

  <div class="box" style="margin-bottom:10px; min-height:auto;">
    <div class="box-title">Seller / المورد</div>
    <div class="row-line"><span class="lbl">الاسم / Name :</span> <span class="val">{{ phase1.company }}</span></div>
    <div class="row-line"><span class="lbl">العنوان / Address :</span>
      <span class="val">
        {% if street %}{{ street }}{% endif %}
        {% if district %}{% if street %} - {% endif %}{{ district }}{% endif %}
        {% if city %}{% if street or district %} - {% endif %}{{ city }}{% endif %}
        {% if postal_code %} | {{ postal_code }}{% endif %}
      </span>
    </div>
    <div class="row-line"><span class="lbl">سجل تجاري / CRN :</span> <span class="val en">{{ seller_crn or "" }}</span></div>
    <div class="row-line"><span class="lbl">الرقم الضريبي / VAT NO. :</span> <span class="val en">{{ phase1.vat_registration_number or "" }}</span></div>
  </div>

  <table class="items">
    <thead>
      <tr>
        <th style="width:28%">تفاصيل السلع أو الخدمات<br><span class="en">Natures of goods or services</span></th>
        <th style="width:10%">الوحدة<br><span class="en">Unit</span></th>
        <th style="width:10%">الكمية<br><span class="en">Quantity</span></th>
        <th style="width:12%">سعر الوحدة<br><span class="en">Unit price</span></th>
        <th style="width:12%">الإجمالي<br><span class="en">Total</span></th>
        <th style="width:12%">الخصومات<br><span class="en">Discount</span></th>
        <th style="width:16%">المجموع<br><span class="en">Item Subtotal</span></th>
      </tr>
    </thead>
    <tbody>
      {% for row in doc.items %}
      {% set line_discount = (row.discount_amount or 0) | abs %}
      <tr>
        <td class="desc">{{ row.item_name }}</td>
        <td>{{ row.uom or "" }}</td>
        <td class="en">{{ row.qty | abs }}</td>
        <td class="en">{{ "%.2f"|format(row.rate | abs) }}</td>
        <td class="en">{{ "%.2f"|format(row.amount | abs) }}</td>
        <td class="en">{{ "%.2f"|format(line_discount) }}</td>
        <td class="en">{{ "%.2f"|format(row.net_amount | abs) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  {% set invoice_total = doc.total | abs %}
  {% set invoice_net = doc.net_total | abs %}
  {% set invoice_discount = (invoice_total - invoice_net) if (invoice_total - invoice_net) > 0 else 0 %}
  {% set amount_words = get_arabic_amount_in_words(doc.grand_total | abs, doc.currency) %}

  <div class="totals-wrap">
    <div class="totals-left">
      <div class="words-box" style="margin-top:0;">
        <div class="words-label">المبلغ كتابة :</div>
        <div class="words-value">{{ amount_words }}</div>
      </div>
    </div>
    <div class="totals-right">
      <table class="totals">
        <tr>
          <td class="k">الإجمالي (غير شامل ضريبة القيمة المضافة)<br><span class="en">Total (Tax not included)</span></td>
          <td class="v">{{ "%.2f"|format(invoice_total) }}</td>
        </tr>
        <tr>
          <td class="k">مجموع الخصومات / Discount</td>
          <td class="v">{{ "%.2f"|format(invoice_discount) }}</td>
        </tr>
        <tr>
          <td class="k">الصافي قبل الضريبة<br><span class="en">Net (Tax not included)</span></td>
          <td class="v">{{ "%.2f"|format(invoice_net) }}</td>
        </tr>
        <tr>
          <td class="k">ضريبة القيمة المضافة / Total VAT</td>
          <td class="v">{{ "%.2f"|format((doc.total_taxes_and_charges or 0) | abs) }}</td>
        </tr>
        <tr>
          <td class="k">إجمالي المبلغ المستحق / Total Amount Due</td>
          <td class="v">{{ "%.2f"|format(doc.grand_total | abs) }}</td>
        </tr>
      </table>
    </div>
  </div>
</div>
{% endif %}
"""


def run():
	if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
		doc = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
	else:
		doc = frappe.new_doc("Print Format")
		doc.name = PRINT_FORMAT_NAME

	doc.update(
		{
			"doc_type": "Sales Invoice",
			"module": "Ndserp",
			"standard": "No",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"default_print_language": "ar",
			"disabled": 0,
			"html": HTML.strip(),
			"css": "",
			"margin_top": 10,
			"margin_bottom": 10,
			"margin_left": 10,
			"margin_right": 10,
			"page_number": "Hide",
			"font_size": 12,
			"line_breaks": 0,
			"show_section_headings": 0,
			"align_labels_right": 0,
			"absolute_value": 0,
			"raw_printing": 0,
			"print_format_builder": 0,
			"print_format_builder_beta": 0,
		}
	)
	doc.save(ignore_permissions=True)

	# Default print format for Sales Invoice
	existing = frappe.db.exists(
		"Property Setter",
		{"doc_type": "Sales Invoice", "property": "default_print_format", "doctype_or_field": "DocType"},
	)
	if existing:
		ps = frappe.get_doc("Property Setter", existing)
		ps.value = PRINT_FORMAT_NAME
		ps.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocType",
				"doc_type": "Sales Invoice",
				"property": "default_print_format",
				"property_type": "Data",
				"value": PRINT_FORMAT_NAME,
			}
		).insert(ignore_permissions=True)

	frappe.db.commit()
	return {"print_format": PRINT_FORMAT_NAME, "default_set": True}
