/**
 * POS Sync Store
 *
 * Manages offline synchronization state and operations for the POS system.
 * Handles invoice caching, sync operations, and offline state management.
 *
 * Key Design Decision:
 * This store subscribes directly to offlineState instead of using the useOffline()
 * composable. This is intentional because Pinia stores are singletons that persist
 * across component remounts (e.g., when changing language). Using Vue lifecycle
 * hooks (onMounted/onUnmounted) from composables would cause the subscription to
 * break when components remount.
 *
 * @module stores/posSync
 */

import { useToast } from "@/composables/useToast"
import {
	cacheCustomersFromServer,
	cachePaymentMethodsFromServer,
	cacheReturnableInvoicesFromServer,
	notifyInvoicesSynced,
	syncOfflineInvoices,
} from "@/utils/offline"
import { logger } from "@/utils/logger"
import { offlineState } from "@/utils/offline/offlineState"
import { offlineWorker } from "@/utils/offline/workerClient"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

const log = logger.create('POSSync')

export const usePOSSyncStore = defineStore("posSync", () => {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Current offline status - synced with offlineState singleton */
	const isOffline = ref(offlineState.isOffline)

	/** Number of invoices pending sync */
	const pendingInvoicesCount = ref(0)

	/** Whether a sync operation is in progress */
	const isSyncing = ref(false)

	/** Current connection quality metrics */
	const connectionQuality = ref(offlineState.getConnectionQuality())

	/** List of pending invoices for display */
	const pendingInvoicesList = ref([])

	/** Track previous offline state for detecting online/offline transitions */
	let wasOffline = offlineState.isOffline

	/** Periodic auto-sync interval (2 minutes while online with pending invoices) */
	const AUTO_SYNC_INTERVAL_MS = 2 * 60 * 1000
	let autoSyncTimerId = null

	function startAutoSyncTimer() {
		if (autoSyncTimerId) return
		autoSyncTimerId = setInterval(async () => {
			if (isOffline.value || isSyncing.value) return
			if (pendingInvoicesCount.value === 0) return
			log.info('Periodic auto-sync: pending invoices detected')
			try {
				const result = await syncPending()
				notifyInvoicesSynced(result)
				if (result.success > 0) {
					showSuccess(__('{0} invoice(s) synced automatically', [result.success]))
				}
			} catch (error) {
				log.error('Periodic auto-sync failed', error)
			}
		}, AUTO_SYNC_INTERVAL_MS)
	}

	function stopAutoSyncTimer() {
		if (autoSyncTimerId) {
			clearInterval(autoSyncTimerId)
			autoSyncTimerId = null
		}
	}

	// =========================================================================
	// TOAST NOTIFICATIONS
	// =========================================================================

	const { showSuccess, showError, showWarning } = useToast()

	// =========================================================================
	// OFFLINE STATE SUBSCRIPTION
	// =========================================================================

	/**
	 * Subscribe to offlineState changes at the store level.
	 * This subscription persists for the app's lifetime since Pinia stores are singletons.
	 */
	offlineState.subscribe(async (state) => {
		const nowOffline = state.isOffline

		// Update reactive state
		isOffline.value = nowOffline
		connectionQuality.value = state.quality || offlineState.getConnectionQuality()

		// Auto-sync when transitioning from offline to online
		if (wasOffline && !nowOffline) {
			log.info('Transition to online detected, auto-syncing pending invoices')
			try {
				const result = await syncPending()
				notifyInvoicesSynced(result)
				if (result.success > 0) {
					showSuccess(__('{0} invoice(s) synced automatically', [result.success]))
				}
			} catch (error) {
				log.error('Auto-sync failed on reconnection', error)
			}
		}

		// Manage periodic auto-sync timer
		if (nowOffline) {
			stopAutoSyncTimer()
		} else {
			startAutoSyncTimer()
		}

		wasOffline = nowOffline
	})

	// =========================================================================
	// COMPUTED
	// =========================================================================

	/** Whether there are any pending invoices to sync */
	const hasPendingInvoices = computed(() => pendingInvoicesCount.value > 0)

	// =========================================================================
	// INTERNAL HELPERS
	// =========================================================================

	/**
	 * Update the pending invoices count from the worker
	 */
	async function updatePendingCount() {
		try {
			pendingInvoicesCount.value = await offlineWorker.getOfflineInvoiceCount()
		} catch (error) {
			log.error('Failed to get pending invoice count', error)
		}
	}

	/**
	 * Sync pending invoices to the server
	 * @throws {Error} If called while offline
	 */
	async function syncPending() {
		if (isOffline.value) {
			throw new Error("Cannot sync while offline")
		}

		isSyncing.value = true
		try {
			const result = await syncOfflineInvoices()
			await updatePendingCount()
			return result
		} catch (error) {
			log.error('Failed to sync invoices', error)
			throw error
		} finally {
			isSyncing.value = false
		}
	}

	/**
	 * Get all pending invoices from the worker
	 */
	async function getPending() {
		return await offlineWorker.getOfflineInvoices()
	}

	/**
	 * Delete a pending invoice by ID
	 * @param {string} id - Invoice ID to delete
	 */
	async function deletePending(id) {
		await offlineWorker.deleteOfflineInvoice(id)
		await updatePendingCount()
	}

	/**
	 * Cache items and customers for offline use
	 * @param {Array} items - Items to cache
	 * @param {Array} customers - Customers to cache
	 */
	async function cacheData(items, customers) {
		try {
			if (items?.length > 0) {
				await offlineWorker.cacheItems(items)
			}
			if (customers?.length > 0) {
				await offlineWorker.cacheCustomers(customers)
			}
			return true
		} catch (error) {
			log.error('Failed to cache data', error)
			return false
		}
	}

	// =========================================================================
	// PUBLIC ACTIONS
	// =========================================================================

	/**
	 * Save an invoice offline for later sync
	 * @param {Object} invoiceData - Invoice data to save
	 */
	async function saveInvoiceOffline(invoiceData) {
		try {
			await offlineWorker.saveOfflineInvoice(invoiceData)
			await updatePendingCount()
			log.info('Invoice saved offline successfully')

			// Auto-sync immediately if online
			if (!isOffline.value && !isSyncing.value) {
				try {
					const result = await syncPending()
					notifyInvoicesSynced(result)
					if (result.success > 0) {
						showSuccess(__('{0} invoice(s) synced automatically', [result.success]))
					}
				} catch (syncError) {
					log.error('Auto-sync after offline save failed', syncError)
				}
			}

			return true
		} catch (error) {
			log.error('Failed to save invoice offline', error)
			throw error
		}
	}

	/**
	 * Load the list of pending invoices for display
	 */
	async function loadPendingInvoices() {
		try {
			pendingInvoicesList.value = await getPending()
		} catch (error) {
			log.error('Failed to load pending invoices', error)
			pendingInvoicesList.value = []
		}
	}

	/**
	 * Delete an offline invoice by ID with user feedback
	 * @param {string} invoiceId - Invoice ID to delete
	 */
	async function deleteOfflineInvoice(invoiceId) {
		try {
			await deletePending(invoiceId)
			await loadPendingInvoices()
			showSuccess(__("Offline invoice deleted successfully"))
		} catch (error) {
			log.error('Failed to delete offline invoice', error)
			showError(error.message || __("Failed to delete offline invoice"))
			throw error
		}
	}

	/**
	 * Sync all pending invoices with user feedback
	 * @returns {Object} Sync result with success/failed counts
	 */
	async function syncAllPending() {
		if (isOffline.value) {
			showWarning(__("Cannot sync while offline"))
			return { success: 0, failed: 0, errors: [] }
		}

		try {
			const result = await syncPending()

			if (result.success > 0) {
				showSuccess(__('{0} invoice(s) synced successfully', [result.success]))
				await loadPendingInvoices()
			}

			return result
		} catch (error) {
			log.error('Sync all pending failed', error)
			throw error
		}
	}

	/**
	 * Preload data for offline use (payment methods, customers)
	 * @param {Object} currentProfile - Current POS profile
	 */
	async function preloadDataForOffline(currentProfile) {
		if (!currentProfile || isOffline.value) {
			return
		}

		try {
			const cacheReady = await checkCacheReady()
			const stats = await getCacheStats()
			const needsRefresh = !stats.lastSync || Date.now() - stats.lastSync > 24 * 60 * 60 * 1000

			// Always load payment methods for reliable offline support
			log.info('Loading payment methods for offline use')
			try {
				const paymentMethodsData = await cachePaymentMethodsFromServer(currentProfile.name)

				if (paymentMethodsData.payment_methods?.length > 0) {
					const methodsWithProfile = paymentMethodsData.payment_methods.map((method) => ({
						...method,
						pos_profile: currentProfile.name,
					}))
					await offlineWorker.cachePaymentMethods(methodsWithProfile)
					log.success(`Cached ${methodsWithProfile.length} payment methods`)
				}
			} catch (error) {
				log.error('Failed to load payment methods', error)
				// Continue with other data loading
			}

			// Load customers if cache needs refresh
			if (!cacheReady || needsRefresh) {
				showSuccess(__("Loading customers for offline use..."))

				const customersData = await cacheCustomersFromServer(currentProfile.name)
				await cacheData([], customersData.customers || [])

				showSuccess(__("Data is ready for offline use"))
			}

			// Cache returnable invoices for offline returns
			log.info("Caching returnable invoices for offline returns")
			try {
				const returnCache = await cacheReturnableInvoicesFromServer(50)
				if (returnCache.count > 0) {
					log.success(`Cached ${returnCache.count} returnable invoices`)
				}
			} catch (error) {
				log.error("Failed to cache returnable invoices", error)
			}
		} catch (error) {
			log.error('Failed to preload offline data', error)
			showWarning(__("Some data may not be available offline"))
		}
	}

	/**
	 * Check if offline cache is available and warn user if not
	 * @returns {boolean} Whether cache is ready
	 */
	async function checkOfflineCacheAvailability() {
		const cacheReady = await checkCacheReady()
		if (!cacheReady && isOffline.value) {
			showWarning(__("POS is offline without cached data. Please connect to sync."))
		}
		return cacheReady
	}

	/**
	 * Check if the offline cache is ready
	 */
	async function checkCacheReady() {
		return await offlineWorker.isCacheReady()
	}

	/**
	 * Get cache statistics
	 */
	async function getCacheStats() {
		return await offlineWorker.getCacheStats()
	}

	// =========================================================================
	// INITIALIZATION
	// =========================================================================

	// Initialize pending count on store creation
	updatePendingCount()
	startAutoSyncTimer()

	// =========================================================================
	// EXPORTS
	// =========================================================================

	return {
		// State
		isOffline,
		pendingInvoicesCount,
		isSyncing,
		pendingInvoicesList,

		// Computed
		hasPendingInvoices,

		// Actions
		saveInvoiceOffline,
		loadPendingInvoices,
		deleteOfflineInvoice,
		syncAllPending,
		preloadDataForOffline,
		checkOfflineCacheAvailability,
		checkCacheReady,
		getCacheStats,
	}
})
