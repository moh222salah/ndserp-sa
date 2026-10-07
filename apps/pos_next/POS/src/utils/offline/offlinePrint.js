/**
 * Small helpers for offline print and default-customer fallback.
 * Does not block network requests globally.
 */

import { offlineWorker } from "./workerClient"

export function isBrowserOffline() {
	return typeof navigator !== "undefined" && navigator.onLine === false
}

export function isLocalInvoiceName(name) {
	return typeof name === "string" && name.startsWith("OFFLINE-")
}

export function createOfflineInvoiceName() {
	return `OFFLINE-${Date.now()}`
}

export function readCachedDefaultCustomer(posProfileName) {
	if (typeof localStorage === "undefined") return null

	try {
		const stored = localStorage.getItem(
			`pos_next_default_customer:${posProfileName}`,
		)
		if (stored) {
			return JSON.parse(stored)
		}

		const shiftRaw = localStorage.getItem("pos_shift_data")
		if (!shiftRaw) return null

		const shift = JSON.parse(shiftRaw)
		const profile = shift.pos_profile || {}
		if (!profile.customer) return null

		return {
			name: profile.customer,
			customer_name: profile.customer_name || profile.customer,
			customer_group: profile.customer_group,
		}
	} catch {
		return null
	}
}

export function cacheDefaultCustomer(posProfileName, customer) {
	if (!posProfileName || !customer?.name || typeof localStorage === "undefined") {
		return
	}

	try {
		localStorage.setItem(
			`pos_next_default_customer:${posProfileName}`,
			JSON.stringify(customer),
		)
	} catch {
		// ignore quota / private mode
	}
}

/**
 * Build a printable invoice document from offline queue / cart data.
 */
export function normalizeInvoiceForPrint(raw = {}, invoiceName = null) {
	const data = raw.data || raw
	const name = invoiceName || data.name || createOfflineInvoiceName()
	const customerCode = data.customer
	const customerName =
		data.customer_name ||
		(typeof customerCode === "object"
			? customerCode.customer_name
			: null) ||
		customerCode

	const items = (data.items || []).map((item) => ({
		...item,
		qty: item.qty ?? item.quantity ?? 0,
		quantity: item.quantity ?? item.qty ?? 0,
	}))

	const payments = (data.payments || []).map((payment) => ({
		...payment,
		amount: payment.amount ?? payment.base_amount ?? 0,
	}))

	const paidAmount = payments.reduce(
		(sum, payment) => sum + Number.parseFloat(payment.amount || 0),
		0,
	)

	return {
		...data,
		name,
		doctype: data.doctype || "Sales Invoice",
		is_offline: true,
		customer: typeof customerCode === "object" ? customerCode.name : customerCode,
		customer_name: customerName,
		items,
		payments,
		grand_total: data.grand_total ?? 0,
		total_tax: data.total_tax ?? 0,
		total_discount: data.total_discount ?? 0,
		posting_date: data.posting_date || new Date().toISOString().slice(0, 10),
		paid_amount: data.paid_amount ?? paidAmount,
		outstanding_amount: Math.max(
			0,
			Number.parseFloat(data.grand_total || 0) - paidAmount,
		),
	}
}

export async function getOfflineInvoiceByName(invoiceName) {
	if (!invoiceName) return null

	try {
		const invoices = await offlineWorker.getOfflineInvoices()
		const match = invoices.find((entry) => {
			const dataName = entry?.data?.name
			if (dataName && dataName === invoiceName) return true
			if (isLocalInvoiceName(invoiceName)) {
				const ts = invoiceName.replace("OFFLINE-", "")
				return String(entry?.timestamp) === ts
			}
			return false
		})

		if (!match) return null
		return normalizeInvoiceForPrint(match, invoiceName)
	} catch {
		return null
	}
}
