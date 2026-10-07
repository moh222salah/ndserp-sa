import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import {
	getOfflineInvoiceByName,
	isBrowserOffline,
	isLocalInvoiceName,
	normalizeInvoiceForPrint,
} from "@/utils/offline/offlinePrint"
import * as qzTray from "@/utils/qzTray"

const log = logger.create("PrintInvoice")

export function shouldPrintLocally(invoiceData = {}) {
	return Boolean(
		invoiceData.is_offline ||
			isLocalInvoiceName(invoiceData.name) ||
			isBrowserOffline(),
	)
}

async function resolveInvoiceDoc(invoiceDataOrName) {
	if (invoiceDataOrName && typeof invoiceDataOrName === "object") {
		if (Array.isArray(invoiceDataOrName.items) && invoiceDataOrName.items.length) {
			return normalizeInvoiceForPrint(invoiceDataOrName, invoiceDataOrName.name)
		}
		if (
			Array.isArray(invoiceDataOrName.data?.items) &&
			invoiceDataOrName.data.items.length
		) {
			return normalizeInvoiceForPrint(
				invoiceDataOrName,
				invoiceDataOrName.name || invoiceDataOrName.data?.name,
			)
		}
		const localName = invoiceDataOrName.name || invoiceDataOrName.offline_id
		if (localName) {
			const cached = await getOfflineInvoiceByName(localName)
			if (cached) return cached
		}
		return invoiceDataOrName.name ? invoiceDataOrName : null
	}

	if (typeof invoiceDataOrName === "string") {
		const cached = await getOfflineInvoiceByName(invoiceDataOrName)
		if (cached) return cached
		if (isLocalInvoiceName(invoiceDataOrName) || isBrowserOffline()) {
			return null
		}
		return await call("pos_next.api.invoices.get_invoice", {
			invoice_name: invoiceDataOrName,
		})
	}

	return null
}

const DEFAULT_CASHIER_FORMAT = "POS Next Receipt"
const DEFAULT_KITCHEN_FORMAT = "POS Next Kitchen Ticket"
const DEFAULT_SHIFT_FORMAT = "POS Next End of Shift Report"

/**
 * Normalize print settings from a POS Profile document or print_settings payload.
 */
export function normalizePrintSettings(source = {}) {
	const fromNested = source.print_settings || {}
	return {
		auto_print:
			fromNested.auto_print ??
			source.print_receipt_on_order_complete ??
			0,
		print_format:
			fromNested.print_format ||
			source.print_format ||
			DEFAULT_CASHIER_FORMAT,
		letter_head: fromNested.letter_head || source.letter_head || null,
		print_method:
			fromNested.print_method ||
			source.posa_print_method ||
			"Browser",
		cashier_printer:
			fromNested.cashier_printer ||
			source.posa_cashier_printer ||
			"",
		kitchen_printer:
			fromNested.kitchen_printer ||
			source.posa_kitchen_printer ||
			"",
		kitchen_print_format:
			fromNested.kitchen_print_format ||
			source.posa_kitchen_print_format ||
			DEFAULT_KITCHEN_FORMAT,
		print_kitchen_ticket: Number(
			fromNested.print_kitchen_ticket ??
				source.posa_print_kitchen_ticket ??
				0,
		),
	}
}

/**
 * Resolve print settings for an invoice / POS Profile.
 * Prefers an explicit profile object (e.g. from shift store) to avoid extra fetches.
 */
export async function resolvePrintSettings({
	invoiceData = null,
	posProfile = null,
	printFormat = null,
	letterhead = null,
} = {}) {
	let profileDoc = posProfile

	if (!profileDoc && invoiceData?.pos_profile && !isBrowserOffline()) {
		try {
			profileDoc = await call("frappe.client.get", {
				doctype: "POS Profile",
				name: invoiceData.pos_profile,
			})
		} catch (error) {
			log.warn("Could not fetch POS Profile print settings:", error)
		}
	}

	const settings = normalizePrintSettings(profileDoc || {})
	if (printFormat) {
		settings.print_format = printFormat
	}
	if (letterhead !== null && letterhead !== undefined) {
		settings.letter_head = letterhead
	}
	return settings
}

function openBrowserPrint(invoiceData, printFormat, letterhead = null) {
	const doctype = invoiceData.doctype || "Sales Invoice"
	const format = printFormat || DEFAULT_CASHIER_FORMAT

	const params = new URLSearchParams({
		doctype: doctype,
		name: invoiceData.name,
		format: format,
		no_letterhead: letterhead ? 0 : 1,
		_lang: "en",
		trigger_print: 1,
		_t: Date.now(),
	})

	if (letterhead) {
		params.append("letterhead", letterhead)
	}

	const printUrl = `/printview?${params.toString()}`
	const printWindow = window.open(printUrl, "_blank", "width=800,height=600")

	if (!printWindow) {
		throw new Error(
			"Failed to open print window. Please check your popup blocker settings.",
		)
	}

	return true
}

async function fetchPrintHtml(invoiceData, printFormat, letterhead = null) {
	const doctype = invoiceData.doctype || "Sales Invoice"
	const result = await call("frappe.www.printview.get_html_and_style", {
		doc: doctype,
		name: invoiceData.name,
		print_format: printFormat || DEFAULT_CASHIER_FORMAT,
		no_letterhead: letterhead ? 0 : 1,
		letterhead: letterhead || undefined,
	})

	const payload = result?.message || result || {}
	if (!payload.html) {
		throw new Error("Empty print HTML returned")
	}
	return payload
}

async function printViaQz(invoiceData, printFormat, printerName, letterhead = null) {
	const { html, style } = await fetchPrintHtml(
		invoiceData,
		printFormat,
		letterhead,
	)
	await qzTray.printHtml(printerName, html, style || "")
	return true
}

/**
 * Print a document with Browser or QZ Tray based on settings.
 * Falls back to browser (then custom HTML) if QZ fails.
 */
export async function printWithSettings(
	invoiceData,
	settings,
	{
		role = "cashier",
		printFormat = null,
		printerName = null,
		letterhead = null,
	} = {},
) {
	if (!invoiceData || !invoiceData.name) {
		throw new Error("Invalid invoice data")
	}

	if (shouldPrintLocally(invoiceData)) {
		printInvoiceCustom(invoiceData)
		return { method: "custom-offline", success: true }
	}

	const format =
		printFormat ||
		(role === "kitchen"
			? settings.kitchen_print_format || DEFAULT_KITCHEN_FORMAT
			: settings.print_format || DEFAULT_CASHIER_FORMAT)

	const printer =
		printerName ||
		(role === "kitchen"
			? settings.kitchen_printer
			: settings.cashier_printer)

	const method = settings.print_method || "Browser"
	const useQz = method === "QZ Tray" && printer

	if (useQz) {
		try {
			await printViaQz(
				invoiceData,
				format,
				printer,
				letterhead || settings.letter_head,
			)
			return { method: "qz", success: true }
		} catch (error) {
			log.error("QZ print failed, falling back to browser:", error)
			try {
				openBrowserPrint(
					invoiceData,
					format,
					letterhead || settings.letter_head,
				)
				return {
					method: "browser-fallback",
					success: true,
					warning: error.message,
				}
			} catch (browserError) {
				log.error("Browser fallback failed:", browserError)
				if (role === "cashier") {
					printInvoiceCustom(invoiceData)
					return {
						method: "custom-fallback",
						success: true,
						warning: error.message,
					}
				}
				throw browserError
			}
		}
	}

	try {
		openBrowserPrint(
			invoiceData,
			format,
			letterhead || settings.letter_head,
		)
		return { method: "browser", success: true }
	} catch (error) {
		log.error("Error printing with Frappe print format:", error)
		if (role === "cashier") {
			printInvoiceCustom(invoiceData)
			return { method: "custom-fallback", success: true }
		}
		throw error
	}
}

/**
 * Print invoice using Frappe's print format system (cashier receipt).
 * @param {Object} invoiceData - The invoice document data
 * @param {string} printFormat - The print format name (optional)
 * @param {string} letterhead - The letterhead name (optional)
 * @param {Object} [posProfile] - Optional POS Profile / print settings object
 * @note Use "POS Next Receipt" format for thermal printer (80mm) or configure via POS Profile
 */
export async function printInvoice(
	invoiceData,
	printFormat = null,
	letterhead = null,
	posProfile = null,
) {
	const settings = await resolvePrintSettings({
		invoiceData,
		posProfile,
		printFormat,
		letterhead,
	})
	return printWithSettings(invoiceData, settings, {
		role: "cashier",
		printFormat: settings.print_format,
		letterhead: settings.letter_head,
	})
}

/**
 * Generates and prints a custom POS receipt using a thermal printer layout.
 *
 * This fallback printer is used when Frappe's standard print format is unavailable.
 * The receipt is optimized for 80mm thermal printers with clean, readable formatting.
 *
 * Receipt Structure:
 * - Header: Company name and invoice type
 * - Info: Invoice number, date, customer, payment status
 * - Items: Each item shows quantity × original price = subtotal
 * - Discounts: Displayed as separate line items with negative amounts
 * - Totals: Subtotal, tax, and grand total
 * - Payments: Payment methods and amounts, change, outstanding balance
 * - Footer: Thank you message and branding
 *
 * @param {Object} invoiceData - The invoice document data from ERPNext
 * @param {string} invoiceData.name - Invoice number
 * @param {string} invoiceData.company - Company name
 * @param {Array} invoiceData.items - Invoice line items
 * @param {Array} invoiceData.payments - Payment records
 * @param {number} invoiceData.grand_total - Invoice total amount
 */
export function printInvoiceCustom(invoiceData) {
	// Open print window with receipt size dimensions (80mm ≈ 302px at 96 DPI)
	const printWindow = window.open("", "_blank", "width=350,height=600")

	const printContent = `
		<!DOCTYPE html>
		<html>
		<head>
			<meta charset="UTF-8">
			<title>${__('Invoice - {0}', [invoiceData.name])}</title>
			<style>
				* {
					margin: 0;
					padding: 0;
					box-sizing: border-box;
				}

				body {
					font-family: 'Courier New', monospace;
					padding: 10px;
					width: 80mm;
					margin: 0;
					max-width: 80mm;
					font-weight: bold;
					color: black;
				}

				.receipt {
					width: 100%;
				}

				.header {
					text-align: center;
					margin-bottom: 20px;
					border-bottom: 2px dashed #000;
					padding-bottom: 10px;
				}

				.company-name {
					font-size: 18px;
					font-weight: bold;
					margin-bottom: 5px;
				}

				.invoice-info {
					margin-bottom: 15px;
					font-size: 12px;
				}

				.invoice-info div {
					display: flex;
					justify-content: space-between;
					margin-bottom: 3px;
				}

				.partial-status {
					color: #000;
					font-weight: bold;
					margin-bottom: 5px;
				}

				.items-table {
					width: 100%;
					margin-bottom: 15px;
					border-top: 1px dashed #000;
					border-bottom: 1px dashed #000;
					padding: 10px 0;
				}

				.item-row {
					margin-bottom: 10px;
					font-size: 12px;
				}

				.item-name {
					font-weight: bold;
					margin-bottom: 3px;
				}

				.item-details {
					display: flex;
					justify-content: space-between;
					font-size: 11px;
					color: #000;
				}

				.item-discount {
					display: flex;
					justify-content: space-between;
					font-size: 10px;
					color: #000;
					margin-top: 2px;
				}

				.item-serials {
					font-size: 9px;
					color: #000;
					margin-top: 3px;
					padding: 3px 5px;
					background-color: #fff;
					border: 1px dashed #000;
					border-radius: 2px;
				}

				.item-serials-label {
					font-weight: bold;
					margin-bottom: 2px;
				}

				.item-serials-list {
					word-break: break-all;
				}

				.totals {
					margin-top: 15px;
					border-top: 1px dashed #000;
					padding-top: 10px;
				}

				.total-row {
					display: flex;
					justify-content: space-between;
					margin-bottom: 5px;
					font-size: 12px;
				}

				.grand-total {
					font-size: 16px;
					font-weight: bold;
					border-top: 2px solid #000;
					padding-top: 10px;
					margin-top: 10px;
				}

				.payments {
					margin-top: 15px;
					border-top: 1px dashed #000;
					padding-top: 10px;
				}

				.payment-row {
					display: flex;
					justify-content: space-between;
					margin-bottom: 3px;
					font-size: 11px;
				}

				.total-paid {
					font-weight: bold;
					border-top: 1px solid #000;
					padding-top: 5px;
					margin-top: 5px;
				}

				.outstanding-row {
					display: flex;
					justify-content: space-between;
					font-size: 13px;
					font-weight: bold;
					color: #000;
					background-color: #fff;
					border: 1px solid #000;
					padding: 8px;
					margin-top: 8px;
					border-radius: 4px;
				}

				.footer {
					text-align: center;
					margin-top: 20px;
					padding-top: 10px;
					border-top: 2px dashed #000;
					font-size: 11px;
				}

				@media print {
					@page {
						size: 80mm auto;
						margin: 0;
					}

					body {
						width: 80mm;
						padding: 5mm;
						margin: 0;
					}

					.no-print {
						display: none;
					}
				}
			</style>
		</head>
		<body>
			<div class="receipt">
				<!-- Header -->
				<div class="header">
					<div class="company-name">${invoiceData.company || "POS Next"}</div>
					${
						invoiceData.company_tax_id
							? `<div style="font-size: 11px;"><strong>${__('VAT:')}</strong> ${invoiceData.company_tax_id}</div>`
							: ""
					}
					${
						invoiceData.customer_group === "Individual"
							? `<div style="font-size: 12px; font-weight: bold;">${__('Simplified Tax Invoice')}</div>
					<div style="font-size: 11px;">${__('SIMPLIFIED TAX INVOICE')}</div>`
							: `<div style="font-size: 12px; font-weight: bold;">${__('Tax Invoice')}</div>
					<div style="font-size: 11px;">${__('TAX INVOICE')}</div>`
					}
				</div>

				<!-- Invoice Info -->
				<div class="invoice-info">
					<div>
						<span>${__('Invoice #:')}</span>
						<span><strong>${invoiceData.name}</strong></span>
					</div>
					<div>
						<span>${__('Date:')}</span>
						<span>${new Date(invoiceData.posting_date || Date.now()).toLocaleString()}</span>
					</div>
					${
						invoiceData.customer_name
							? `
					<div>
						<span>${__('Customer:')}</span>
						<span>${invoiceData.customer_name}</span>
					</div>
					`
							: ""
					}
					${
						invoiceData.tax_id
							? `
					<div>
						<span>${__('Customer VAT:')}</span>
						<span>${invoiceData.tax_id}</span>
					</div>
					`
							: ""
					}
					${
						(invoiceData.status === "Partly Paid" || (invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0 && invoiceData.outstanding_amount < invoiceData.grand_total))
							? `
					<div class="partial-status">
						<span>${__('Status:')}</span>
						<span>${__('PARTIAL PAYMENT')}</span>
					</div>
					`
							: ""
					}
				</div>

				<!-- Items -->
				<div class="items-table">
					${invoiceData.items
						.map((item) => {
							// Determine if item has promotional pricing
							const hasItemDiscount =
								(item.discount_percentage &&
									Number.parseFloat(item.discount_percentage) > 0) ||
								(item.discount_amount &&
									Number.parseFloat(item.discount_amount) > 0)
							const isFree = item.is_free_item
							const qty = item.quantity || item.qty

							// Display original list price for transparency
							const displayRate = item.price_list_rate || item.rate
							// Calculate subtotal before any price reductions
							const subtotal = qty * displayRate

							return `
						<div class="item-row">
							<div class="item-name">
								${item.item_name || item.item_code} ${isFree ? __('(FREE)') : ""}
							</div>
							<div class="item-details">
								<span>${qty} × ${formatCurrency(displayRate)}</span>
								<span><strong>${formatCurrency(subtotal)}</strong></span>
							</div>
							${
								hasItemDiscount
									? `
							<div class="item-discount">
								<span>Discount ${item.discount_percentage ? `(${Number(item.discount_percentage).toFixed(2)}%)` : ""}</span>
								<span>-${formatCurrency(item.discount_amount || 0)}</span>
							</div>
							`
									: ""
							}
							${
								item.serial_no
									? `
							<div class="item-serials">
								<div class="item-serials-label">${__('Serial No:')}</div>
								<div class="item-serials-list">${item.serial_no.replace(/\n/g, ', ')}</div>
							</div>
							`
									: ""
							}
						</div>
						`
						})
						.join("")}
				</div>

				<!-- Totals -->
				<div class="totals">
					${
						invoiceData.total_taxes_and_charges &&
						invoiceData.total_taxes_and_charges > 0
							? `
					<div class="total-row">
						<span>${__('Subtotal:')}</span>
						<span>${formatCurrency((invoiceData.grand_total || 0) - (invoiceData.total_taxes_and_charges || 0))}</span>
					</div>
					<div class="total-row">
						<span>${__('Tax:')}</span>
						<span>${formatCurrency(invoiceData.total_taxes_and_charges)}</span>
					</div>
					`
							: ""
					}
					${
						invoiceData.discount_amount
							? `
					<div class="total-row" style="color: #28a745;">
						<span>Additional Discount${invoiceData.additional_discount_percentage ? ` (${Number(invoiceData.additional_discount_percentage).toFixed(1)}%)` : ""}:</span>
						<span>-${formatCurrency(Math.abs(invoiceData.discount_amount))}</span>
					</div>
					`
							: ""
					}
					<div class="total-row grand-total">
						<span>${__('TOTAL:')}</span>
						<span>${formatCurrency(invoiceData.grand_total)}</span>
					</div>
				</div>

				<!-- Payments -->
				${
					invoiceData.payments && invoiceData.payments.length > 0
						? `
				<div class="payments">
					<div style="font-weight: bold; margin-bottom: 5px; font-size: 12px;">Payments:</div>
					${invoiceData.payments
						.map(
							(payment) => `
						<div class="payment-row">
							<span>${payment.mode_of_payment}:</span>
							<span>${formatCurrency(payment.amount)}</span>
						</div>
					`,
						)
						.join("")}
					<div class="payment-row total-paid">
						<span>${__('Total Paid:')}</span>
						<span>${formatCurrency(invoiceData.paid_amount || 0)}</span>
					</div>
					${
						invoiceData.change_amount && invoiceData.change_amount > 0
							? `
					<div class="payment-row" style="font-weight: bold; margin-top: 5px;">
						<span>${__('Change:')}</span>
						<span>${formatCurrency(invoiceData.change_amount)}</span>
					</div>
					`
							: ""
					}
					${
						invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0
							? `
					<div class="outstanding-row">
						<span>${__('BALANCE DUE:')}</span>
						<span>${formatCurrency(invoiceData.outstanding_amount)}</span>
					</div>
					`
							: ""
					}
				</div>
				`
						: ""
				}

				<!-- Footer -->
				<div class="footer">
					<div style="margin-bottom: 5px;">${__('Thank you for your business!')}</div>
					<div style="font-size: 10px;">Powered by <a href="https://nexus.brainwise.me" target="_blank" style="color: #3b82f6; text-decoration: none; font-weight: 600;">BrainWise</a></div>
				</div>
			</div>

			<div class="no-print" style="text-align: center; margin-top: 20px;">
				<button onclick="window.print()" style="padding: 10px 20px; font-size: 14px; cursor: pointer;">
					${__('Print Receipt')}
				</button>
				<button onclick="window.close()" style="padding: 10px 20px; font-size: 14px; cursor: pointer; margin-left: 10px;">
					${__('Close')}
				</button>
			</div>
		</body>
		</html>
	`

	printWindow.document.write(printContent)
	printWindow.document.close()

	// Auto print after load
	printWindow.onload = () => {
		setTimeout(() => {
			printWindow.print()
		}, 250)
	}
}

function formatCurrency(amount) {
	return Number.parseFloat(amount || 0).toFixed(2)
}

/**
 * Print invoice by name, fetching print format from POS Profile
 * @param {string} invoiceName - The name of the invoice to print
 * @param {string} printFormat - Optional print format override
 * @param {string} letterhead - Optional letterhead override
 * @param {Object} [posProfile] - Optional POS Profile object from shift store
 */
export async function printInvoiceByName(
	invoiceName,
	printFormat = null,
	letterhead = null,
	posProfile = null,
) {
	try {
		const invoiceDoc = await resolveInvoiceDoc(invoiceName)

		if (!invoiceDoc) {
			throw new Error("Invoice not found")
		}

		const settings = await resolvePrintSettings({
			invoiceData: invoiceDoc,
			posProfile,
			printFormat,
			letterhead,
		})

		return await printWithSettings(invoiceDoc, settings, {
			role: "cashier",
			printFormat: settings.print_format,
			letterhead: settings.letter_head,
		})
	} catch (error) {
		log.error("Error fetching invoice for print:", error)
		throw error
	}
}

/**
 * Print kitchen ticket for an invoice document or by name.
 */
export async function printKitchenTicket(invoiceDataOrName, posProfile = null) {
	let invoiceDoc = invoiceDataOrName
	if (typeof invoiceDataOrName === "string") {
		invoiceDoc = await resolveInvoiceDoc(invoiceDataOrName)
	}
	if (!invoiceDoc?.name) {
		throw new Error("Invalid invoice data for kitchen ticket")
	}

	const settings = await resolvePrintSettings({
		invoiceData: invoiceDoc,
		posProfile,
	})

	return printWithSettings(invoiceDoc, settings, {
		role: "kitchen",
		printFormat: settings.kitchen_print_format || DEFAULT_KITCHEN_FORMAT,
		printerName: settings.kitchen_printer,
		letterhead: null,
	})
}

/**
 * Cashier receipt + optional kitchen ticket after payment complete.
 */
export async function printOnOrderComplete(invoiceDataOrName, posProfile = null) {
	let invoiceDoc = invoiceDataOrName
	if (typeof invoiceDataOrName === "string") {
		invoiceDoc = await resolveInvoiceDoc(invoiceDataOrName)
	}
	if (!invoiceDoc?.name) {
		throw new Error("Invalid invoice data")
	}

	const settings = await resolvePrintSettings({
		invoiceData: invoiceDoc,
		posProfile,
	})

	const results = {
		cashier: null,
		kitchen: null,
	}

	results.cashier = await printWithSettings(invoiceDoc, settings, {
		role: "cashier",
		printFormat: settings.print_format,
		letterhead: settings.letter_head,
	})

	if (settings.print_kitchen_ticket) {
		try {
			results.kitchen = await printWithSettings(invoiceDoc, settings, {
				role: "kitchen",
				printFormat: settings.kitchen_print_format || DEFAULT_KITCHEN_FORMAT,
				printerName: settings.kitchen_printer,
				letterhead: null,
			})
		} catch (error) {
			log.error("Kitchen ticket print failed:", error)
			results.kitchen = { success: false, error: error.message }
		}
	}

	return results
}

/**
 * Print end-of-shift report for a submitted POS Closing Shift document.
 * Uses the same Browser / QZ Tray settings as cashier receipts.
 */
export async function printClosingShift(
	closingShiftName,
	posProfile = null,
	posProfileName = null,
) {
	if (!closingShiftName) {
		throw new Error("Closing shift name is required")
	}

	const doc = { doctype: "POS Closing Shift", name: closingShiftName }
	const settings = await resolvePrintSettings({
		posProfile,
		invoiceData:
			!posProfile && posProfileName ? { pos_profile: posProfileName } : null,
	})

	const format = DEFAULT_SHIFT_FORMAT
	const printer = settings.cashier_printer
	const method = settings.print_method || "Browser"
	const useQz = method === "QZ Tray" && printer

	if (useQz) {
		try {
			await printViaQz(doc, format, printer, settings.letter_head)
			return { method: "qz", success: true }
		} catch (error) {
			log.error("QZ shift report print failed, falling back to browser:", error)
		}
	}

	openBrowserPrint(doc, format, settings.letter_head)
	return { method: "browser", success: true }
}
