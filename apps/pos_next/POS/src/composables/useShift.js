import { createResource } from "frappe-ui"
import { computed, ref } from "vue"

export const shiftState = ref({
	pos_opening_shift: null,
	pos_profile: null,
	company: null,
	isOpen: false,
})

export function useShift() {
	// Check for existing open shift
	const checkOpeningShift = createResource({
		url: "pos_next.api.shifts.check_opening_shift",
		auto: false,
		onSuccess(data) {
			if (data) {
				shiftState.value = {
					pos_opening_shift: data.pos_opening_shift,
					pos_profile: data.pos_profile,
					company: data.company,
					isOpen: true,
				}
				// Store in localStorage for offline support
				localStorage.setItem("pos_shift_data", JSON.stringify(data))
			} else {
				shiftState.value = {
					pos_opening_shift: null,
					pos_profile: null,
					company: null,
					isOpen: false,
				}
				localStorage.removeItem("pos_shift_data")
			}
		},
		onError(error) {
			console.error("Error checking opening shift:", error)
			// Try to load from localStorage
			const cachedData = localStorage.getItem("pos_shift_data")
			if (cachedData) {
				try {
					const data = JSON.parse(cachedData)
					shiftState.value = {
						pos_opening_shift: data.pos_opening_shift,
						pos_profile: data.pos_profile,
						company: data.company,
						isOpen: true,
					}
				} catch (e) {
					console.error("Error parsing cached shift data:", e)
				}
			}
		},
	})

	// Get opening dialog data (POS profiles, payment methods, etc.)
	const getOpeningDialogData = createResource({
		url: "pos_next.api.shifts.get_opening_dialog_data",
		auto: false,
	})

	// Create new opening shift
	const createOpeningShift = createResource({
		url: "pos_next.api.shifts.create_opening_shift",
		makeParams({ pos_profile, company, balance_details }) {
			return {
				pos_profile,
				company,
				balance_details: JSON.stringify(balance_details),
			}
		},
		onSuccess(data) {
			shiftState.value = {
				pos_opening_shift: data.pos_opening_shift,
				pos_profile: data.pos_profile,
				company: data.company,
				isOpen: true,
			}
			// Store in localStorage
			localStorage.setItem("pos_shift_data", JSON.stringify(data))
		},
		onError(error) {
			console.error("Error creating opening shift:", error)
		},
	})

	// Get closing shift data
	const getClosingShiftData = createResource({
		url: "pos_next.api.shifts.get_closing_shift_data",
		makeParams({ opening_shift }) {
			return { opening_shift }
		},
		auto: false,
	})

	// Submit closing shift
	const submitClosingShift = createResource({
		url: "pos_next.api.shifts.submit_closing_shift",
		makeParams({ closing_shift }) {
			return { closing_shift: JSON.stringify(closing_shift) }
		},
		onSuccess() {
			shiftState.value = {
				pos_opening_shift: null,
				pos_profile: null,
				company: null,
				isOpen: false,
			}
			localStorage.removeItem("pos_shift_data")
		},
		onError(error) {
			console.error("Error submitting closing shift:", error)
		},
	})

	// Computed properties
	const hasOpenShift = computed(() => shiftState.value.isOpen)
	const currentShift = computed(() => shiftState.value.pos_opening_shift)
	const currentProfile = computed(() => shiftState.value.pos_profile)
	const currentCompany = computed(() => shiftState.value.company)

	return {
		// State
		shiftState,
		hasOpenShift,
		currentShift,
		currentProfile,
		currentCompany,

		// Resources
		checkOpeningShift,
		getOpeningDialogData,
		createOpeningShift,
		getClosingShiftData,
		submitClosingShift,
	}
}
