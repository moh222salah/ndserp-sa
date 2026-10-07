/**
 * useFormatters composable
 * Provides common formatting functions for use across all components
 */

/**
 * Format currency values to 2 decimal places
 * @param {number} amount - The amount to format
 * @returns {string} Formatted amount with 2 decimal places
 */
function formatCurrency(amount) {
	if (amount === null || amount === undefined) return "0.00"
	return Number.parseFloat(amount).toFixed(2)
}

/**
 * Format quantity values with smart decimal handling
 * Removes trailing zeros for cleaner display
 * @param {number} quantity - The quantity to format
 * @returns {string} Formatted quantity
 */
function formatQuantity(quantity) {
	if (quantity === null || quantity === undefined) return "0"
	const num = Number.parseFloat(quantity)
	// Round to 4 decimal places and remove trailing zeros
	return num.toFixed(4).replace(/\.?0+$/, '')
}

/**
 * Parse a date-like value into a valid Date object.
 * @param {string|Date} value
 * @returns {Date|null}
 */
function parseDateValue(value) {
	if (!value) return null
	if (value instanceof Date) {
		return Number.isNaN(value.getTime()) ? null : value
	}

	const dateTime = new Date(value)
	if (!Number.isNaN(dateTime.getTime())) {
		return dateTime
	}

	const datePart = String(value).slice(0, 10)
	const [year, month, day] = datePart.split("-").map(Number)
	if (year && month && day) {
		const parsed = new Date(year, month - 1, day)
		return Number.isNaN(parsed.getTime()) ? null : parsed
	}

	return null
}

/**
 * Format date and time as d/m/yyyy HH:MM
 * @param {string|Date} datetime - The datetime to format
 * @returns {string} Formatted date and time string
 */
function formatDateTime(datetime) {
	const date = parseDateValue(datetime)
	if (!date) return ""

	const datePart = formatDate(date)
	const hours = String(date.getHours()).padStart(2, "0")
	const minutes = String(date.getMinutes()).padStart(2, "0")
	return `${datePart} ${hours}:${minutes}`
}

/**
 * Format time to HH:MM only (hours and minutes)
 * Handles both Date objects and time strings (e.g., "15:31:22.975239")
 * @param {string|Date} time - The time to format
 * @returns {string} Formatted time string (HH:MM)
 */
function formatTime(time) {
	if (!time) return ""

	// If it's a time string (contains colon), extract HH:MM
	if (typeof time === 'string' && time.includes(':')) {
		const parts = time.split(":")
		if (parts.length >= 2) {
			return `${parts[0]}:${parts[1]}`
		}
		return time
	}

	// If it's a Date object or datetime string, convert and format
	return new Date(time).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
	})
}

/**
 * Format date only as d/m/yyyy
 * @param {string|Date} date - The date to format
 * @returns {string} Formatted date string
 */
function formatDate(date) {
	const parsed = parseDateValue(date)
	if (!parsed) return ""
	return `${parsed.getDate()}/${parsed.getMonth() + 1}/${parsed.getFullYear()}`
}

/**
 * Format percentage values
 * @param {number} value - The value to format as percentage
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted percentage
 */
function formatPercentage(value, decimals = 2) {
	if (value === null || value === undefined) return "0%"
	return `${Number.parseFloat(value).toFixed(decimals).replace(/\.?0+$/, '')}%`
}

/**
 * Composable function to use formatters
 * @returns {Object} Object containing all formatter functions
 */
export function useFormatters() {
	return {
		formatCurrency,
		formatQuantity,
		formatDateTime,
		formatTime,
		formatDate,
		formatPercentage,
	}
}
