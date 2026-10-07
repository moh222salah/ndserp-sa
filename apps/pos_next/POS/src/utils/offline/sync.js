import { call } from "@/utils/apiWrapper"
import { db, getSetting, setSetting } from "./db"
import { offlineState } from "./offlineState"
import { offlineWorker } from "./workerClient"
import { isLocalInvoiceName } from "./offlinePrint"

// Ping server to check connectivity
export const pingServer = async () => {
	if (typeof window === "undefined") return true

	try {
		// Quick ping to check if server is reachable
		const controller = new AbortController()
		const timeoutId = setTimeout(() => controller.abort(), 3000) // 3 second timeout

		const response = await fetch("/api/method/pos_next.api.ping", {
			method: "GET",
			signal: controller.signal,
		})

		clearTimeout(timeoutId)
		const isOnline = response.ok
		// Update centralized state (handles window sync automatically)
		offlineState.setServerOnline(isOnline)
		return isOnline
	} catch (error) {
		// Server unreachable
		offlineState.setServerOnline(false)
		return false
	}
}

// Check if offline - uses centralized state manager
export const isOffline = () => {
	if (typeof window === "undefined") return false
	return offlineState.isOffline
}

// NOTE: Periodic server ping is now handled by the offline worker
// This prevents duplicate pings and centralizes the logic

// Save invoice to offline queue
export const saveOfflineInvoice = async (invoiceData) => {
	try {
		// Validate invoice has items
		if (!invoiceData.items || invoiceData.items.length === 0) {
			throw new Error("Cannot save empty invoice")
		}

		// Clean data (remove reactive properties)
		const cleanData = JSON.parse(JSON.stringify(invoiceData))

		// Add to queue
		await db.invoice_queue.add({
			data: cleanData,
			timestamp: Date.now(),
			synced: false,
			retry_count: 0,
		})

		// Update local stock
		await updateLocalStock(cleanData.items)

		console.log("Invoice saved to offline queue")
		return true
	} catch (error) {
		console.error("Error saving offline invoice:", error)
		throw error
	}
}

// Get pending offline invoices
export const getOfflineInvoices = async () => {
	try {
		// Use filter instead of where/equals for boolean values
		const invoices = await db.invoice_queue
			.filter((invoice) => invoice.synced === false)
			.toArray()
		return invoices
	} catch (error) {
		console.error("Error getting offline invoices:", error)
		return []
	}
}

// Get offline invoice count
export const getOfflineInvoiceCount = async () => {
	try {
		// Use filter instead of where/equals for boolean values
		const count = await db.invoice_queue
			.filter((invoice) => invoice.synced === false)
			.count()
		return count
	} catch (error) {
		console.error("Error getting offline invoice count:", error)
		return 0
	}
}

let syncInProgress = null

// Sync offline invoices to server
export const syncOfflineInvoices = async () => {
	if (isOffline()) {
		console.log("Cannot sync while offline")
		return { success: 0, failed: 0 }
	}

	if (syncInProgress) {
		return syncInProgress
	}

	syncInProgress = _doSyncOfflineInvoices()
	try {
		return await syncInProgress
	} finally {
		syncInProgress = null
	}
}

async function _doSyncOfflineInvoices() {
	const pendingInvoices = await getOfflineInvoices()
	if (pendingInvoices.length === 0) {
		return { success: 0, failed: 0 }
	}

	// Sync sales invoices before returns so return_against exists on server
	const sortedInvoices = [...pendingInvoices].sort((a, b) => {
		const aReturn = a.data?.is_return ? 1 : 0
		const bReturn = b.data?.is_return ? 1 : 0
		return aReturn - bReturn
	})

	let successCount = 0
	let failedCount = 0
	const errors = []

	for (const invoice of sortedInvoices) {
		try {
			// Skip returns whose original invoice is still pending sync
			if (invoice.data?.is_return && invoice.data?.return_against) {
				const returnAgainst = invoice.data.return_against
				const originalPending = sortedInvoices.find(
					(p) =>
						!p.synced &&
						!p.data?.is_return &&
						p.data?.name === returnAgainst,
				)
				if (originalPending) {
					console.log(
						`Skipping return ${invoice.id}: original ${returnAgainst} not synced yet`,
					)
					continue
				}
			}

			const invoiceData = prepareInvoiceForSync(invoice.data)

			const response = await call("pos_next.api.invoices.submit_invoice", {
				data: JSON.stringify({
					invoice: invoiceData,
					data: {},
				}),
			})

			const serverName =
				response?.name ||
				response?.message?.name ||
				response?.message?.message?.name

			if (serverName || response.message || response.name) {
				await db.invoice_queue.update(invoice.id, { synced: true })
				invoice.synced = true
				successCount++

				// Cache submitted invoice for offline returns
				await cacheInvoiceAfterSync(invoice.data, serverName, invoiceData.is_return)
			}
		} catch (error) {
			console.error(`Error syncing invoice ${invoice.id}:`, error)

			errors.push({
				invoiceId: invoice.id,
				customer: invoice.data.customer || "Walk-in Customer",
				error: error,
			})

			await db.invoice_queue.update(invoice.id, {
				retry_count: (invoice.retry_count || 0) + 1,
			})

			failedCount++

			if ((invoice.retry_count || 0) >= 3) {
				await db.invoice_queue.update(invoice.id, {
					sync_failed: true,
					error: error.message,
				})
			}
		}
	}

	const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000
	await db.invoice_queue
		.filter((item) => item.synced === true && item.timestamp < weekAgo)
		.delete()

	return { success: successCount, failed: failedCount, errors }
}

function isLocalItemName(name) {
	return typeof name === "string" && name.startsWith("OFFLINE-")
}

function prepareInvoiceForSync(rawData) {
	const invoiceData = { ...rawData }

	if (invoiceData.items && Array.isArray(invoiceData.items)) {
		invoiceData.items = invoiceData.items.map((item) => {
			const cleanItem = {
				...item,
				qty: item.qty ?? item.quantity ?? 1,
			}
			if (isLocalItemName(cleanItem.name)) {
				delete cleanItem.name
			}
			if (isLocalItemName(cleanItem.sales_invoice_item)) {
				delete cleanItem.sales_invoice_item
			}
			return cleanItem
		})
	}

	// Remove offline-only metadata before server submission
	delete invoiceData.is_offline

	// Offline names never exist on the server — strip so a new doc is created
	if (isLocalInvoiceName(invoiceData.name)) {
		delete invoiceData.name
	}

	if (isLocalInvoiceName(invoiceData.return_against)) {
		delete invoiceData.return_against
	}

	return invoiceData
}

async function cacheInvoiceAfterSync(originalData, serverName, isReturn) {
	if (!serverName) return

	try {
		if (isLocalInvoiceName(originalData.name) && !isReturn) {
			try {
				const fullInvoice = await call("pos_next.api.invoices.get_invoice", {
					invoice_name: serverName,
				})
				const invoiceDoc = fullInvoice?.message || fullInvoice
				if (invoiceDoc?.name) {
					await offlineWorker.remapOfflineInvoiceAfterSync(
						originalData.name,
						invoiceDoc,
					)
					return
				}
			} catch (fetchError) {
				console.warn("Could not fetch full invoice after sync:", fetchError)
			}
		}

		if (isReturn) {
			try {
				const fullInvoice = await call("pos_next.api.invoices.get_invoice", {
					invoice_name: serverName,
				})
				const invoiceDoc = fullInvoice?.message || fullInvoice
				if (invoiceDoc?.name) {
					await offlineWorker.cacheSubmittedInvoice(invoiceDoc)
				}
			} catch (fetchError) {
				console.warn("Could not cache return invoice:", fetchError)
			}
		} else {
			try {
				const fullInvoice = await call("pos_next.api.invoices.get_invoice", {
					invoice_name: serverName,
				})
				const invoiceDoc = fullInvoice?.message || fullInvoice
				if (invoiceDoc?.name) {
					await offlineWorker.cacheSubmittedInvoice(invoiceDoc)
				}
			} catch (fetchError) {
				const fallback = {
					...originalData,
					name: serverName,
					docstatus: 1,
				}
				await offlineWorker.cacheSubmittedInvoice(fallback)
			}
		}
	} catch (error) {
		console.error("Error caching invoice after sync:", error)
	}
}

export const cacheReturnableInvoicesFromServer = async (limit = 50) => {
	if (isOffline()) return { success: false, count: 0 }

	try {
		const invoices = await call("pos_next.api.invoices.get_returnable_invoices", {
			limit,
		})
		const invoiceList = invoices?.message || invoices || []

		if (invoiceList.length > 0) {
			const fullInvoices = []
			for (const summary of invoiceList.slice(0, limit)) {
				try {
					const fullInvoice = await call(
						"pos_next.api.invoices.get_invoice_for_return",
						{ invoice_name: summary.name },
					)
					const invoiceDoc = fullInvoice?.message || fullInvoice
					if (invoiceDoc?.name) {
						fullInvoices.push(invoiceDoc)
					}
				} catch (itemError) {
					console.warn(`Could not cache invoice ${summary.name}:`, itemError)
				}
			}

			if (fullInvoices.length > 0) {
				await offlineWorker.cacheSubmittedInvoices(fullInvoices)
			}

			return { success: true, count: fullInvoices.length }
		}

		return { success: true, count: 0 }
	} catch (error) {
		console.error("Error caching returnable invoices:", error)
		return { success: false, count: 0, error: error.message }
	}
}

// Delete offline invoice
export const deleteOfflineInvoice = async (id) => {
	try {
		await db.invoice_queue.delete(id)
		return true
	} catch (error) {
		console.error("Error deleting offline invoice:", error)
		return false
	}
}

// Update local stock after invoice
export const updateLocalStock = async (items) => {
	try {
		for (const item of items) {
			const stockKey = `${item.item_code}_${item.warehouse}`
			const currentStock = await db.stock.get({
				item_code: item.item_code,
				warehouse: item.warehouse,
			})

			const qty = item.quantity || item.qty || 0
			const newQty = (currentStock?.qty || 0) - qty

			await db.stock.put({
				item_code: item.item_code,
				warehouse: item.warehouse,
				qty: newQty,
				updated_at: Date.now(),
			})
		}
	} catch (error) {
		console.error("Error updating local stock:", error)
	}
}

// Get local stock
export const getLocalStock = async (itemCode, warehouse) => {
	try {
		const stock = await db.stock.get({
			item_code: itemCode,
			warehouse: warehouse,
		})
		return stock?.qty || 0
	} catch (error) {
		console.error("Error getting local stock:", error)
		return 0
	}
}

// Save offline payment
export const saveOfflinePayment = async (paymentData) => {
	try {
		const cleanData = JSON.parse(JSON.stringify(paymentData))

		await db.payment_queue.add({
			data: cleanData,
			timestamp: Date.now(),
			synced: false,
			retry_count: 0,
		})

		console.log("Payment saved to offline queue")
		return true
	} catch (error) {
		console.error("Error saving offline payment:", error)
		throw error
	}
}

// Auto-sync is handled by posSync store (reconnect + periodic retry).
// Dispatch helper for sync completion events.
export function notifyInvoicesSynced(result) {
	if (typeof window === "undefined") return
	window.dispatchEvent(
		new CustomEvent("offlineInvoicesSynced", { detail: result }),
	)
}
