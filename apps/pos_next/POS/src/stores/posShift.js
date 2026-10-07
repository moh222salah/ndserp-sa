import { useShift } from "@/composables/useShift"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

export const usePOSShiftStore = defineStore("posShift", () => {
	// Use the existing shift composable
	const { currentProfile, currentShift, hasOpenShift, checkOpeningShift } =
		useShift()

	// Additional shift state
	const currentTime = ref("")
	const shiftDuration = ref("")

	// Computed
	const profileName = computed(() => currentProfile.value?.name)
	const profileCurrency = computed(
		() => currentProfile.value?.currency || "USD",
	)
	const profileWarehouse = computed(() => currentProfile.value?.warehouse)
	const profileCompany = computed(() => currentProfile.value?.company)
	const profileCustomer = computed(() => currentProfile.value?.customer)
	const autoPrintEnabled = computed(
		() => currentProfile.value?.print_receipt_on_order_complete,
	)
	const printSettings = computed(() => {
		const profile = currentProfile.value || {}
		return {
			auto_print: profile.print_receipt_on_order_complete || 0,
			print_format: profile.print_format || "POS Next Receipt",
			letter_head: profile.letter_head || null,
			print_method: profile.posa_print_method || "Browser",
			cashier_printer: profile.posa_cashier_printer || "",
			kitchen_printer: profile.posa_kitchen_printer || "",
			kitchen_print_format:
				profile.posa_kitchen_print_format || "POS Next Kitchen Ticket",
			print_kitchen_ticket: Number(profile.posa_print_kitchen_ticket || 0),
		}
	})

	function updatePrintSettingsOnProfile(printSettingsUpdate = {}) {
		const profile = currentProfile.value
		if (!profile) return

		if (printSettingsUpdate.print_method !== undefined) {
			profile.posa_print_method = printSettingsUpdate.print_method
		}
		if (printSettingsUpdate.cashier_printer !== undefined) {
			profile.posa_cashier_printer = printSettingsUpdate.cashier_printer
		}
		if (printSettingsUpdate.kitchen_printer !== undefined) {
			profile.posa_kitchen_printer = printSettingsUpdate.kitchen_printer
		}
		if (printSettingsUpdate.kitchen_print_format !== undefined) {
			profile.posa_kitchen_print_format =
				printSettingsUpdate.kitchen_print_format
		}
		if (printSettingsUpdate.print_kitchen_ticket !== undefined) {
			profile.posa_print_kitchen_ticket =
				printSettingsUpdate.print_kitchen_ticket
		}
		if (printSettingsUpdate.print_format !== undefined) {
			profile.print_format = printSettingsUpdate.print_format
		}
		if (printSettingsUpdate.letter_head !== undefined) {
			profile.letter_head = printSettingsUpdate.letter_head
		}

		// Keep offline cache in sync
		try {
			const cached = localStorage.getItem("pos_shift_data")
			if (cached) {
				const data = JSON.parse(cached)
				if (data.pos_profile) {
					Object.assign(data.pos_profile, {
						posa_print_method: profile.posa_print_method,
						posa_cashier_printer: profile.posa_cashier_printer,
						posa_kitchen_printer: profile.posa_kitchen_printer,
						posa_kitchen_print_format: profile.posa_kitchen_print_format,
						posa_print_kitchen_ticket: profile.posa_print_kitchen_ticket,
						print_format: profile.print_format,
						letter_head: profile.letter_head,
					})
					localStorage.setItem("pos_shift_data", JSON.stringify(data))
				}
			}
		} catch (e) {
			// ignore cache sync errors
		}
	}

	// Actions
	function updateShiftDuration() {
		if (!hasOpenShift.value || !currentShift.value?.period_start_date) {
			shiftDuration.value = ""
			return
		}

		const startTime = new Date(currentShift.value.period_start_date)
		const now = new Date()
		const diff = now - startTime

		const hours = Math.floor(diff / (1000 * 60 * 60))
		const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
		const seconds = Math.floor((diff % (1000 * 60)) / 1000)

		shiftDuration.value = `${hours} ${__('Hr')} ${minutes} ${__('Min')} ${seconds} ${__('Sec')}`
	}

	function updateCurrentTime() {
		const now = new Date()
		currentTime.value = now.toLocaleTimeString("en-US", { hour12: false })
	}

	function startTimers() {
		// Update both immediately
		updateCurrentTime()
		updateShiftDuration()

		// Then update every second
		const intervalId = setInterval(() => {
			updateCurrentTime()
			updateShiftDuration()
		}, 1000)

		return intervalId
	}

	async function checkShift() {
		await checkOpeningShift.fetch()
		return hasOpenShift.value
	}

	return {
		// State
		currentProfile,
		currentShift,
		hasOpenShift,
		currentTime,
		shiftDuration,

		// Computed
		profileName,
		profileCurrency,
		profileWarehouse,
		profileCompany,
		profileCustomer,
		autoPrintEnabled,
		printSettings,

		// Actions
		updateShiftDuration,
		updateCurrentTime,
		startTimers,
		checkShift,
		checkOpeningShift,
		updatePrintSettingsOnProfile,
	}
})
