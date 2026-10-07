/**
 * POS Appearance theme engine
 *
 * Ports the Appearance feature from POSNext (exceed-erp.cloud):
 * - Light / Dark display mode
 * - Colour palettes (Blue, Mint, Purple, Red, Amber, Teal)
 *
 * Remaps Tailwind `blue` / `gray` (and supporting) CSS variables at runtime
 * so existing `bg-blue-*` / `text-gray-*` classes pick up the selected theme.
 */

export const ACCENT_STORAGE_KEY = "pos_next_accent"
export const THEME_MODE_STORAGE_KEY = "pos_next_theme_mode"

export const ACCENT_SCALES = {
	blue: {
		id: "blue",
		label: "Blue",
		ramp: [
			"#EFF6FF",
			"#DBEAFE",
			"#BFDBFE",
			"#93C5FD",
			"#60A5FA",
			"#3B82F6",
			"#2563EB",
			"#1D4ED8",
			"#1E40AF",
			"#1E3A8A",
		],
	},
	mint: {
		id: "mint",
		label: "Mint",
		ramp: [
			"#ECFDF5",
			"#D1FAE5",
			"#A7F3D0",
			"#6EE7B7",
			"#34D399",
			"#10B981",
			"#059669",
			"#047857",
			"#065F46",
			"#064E3B",
		],
	},
	purple: {
		id: "purple",
		label: "Purple",
		ramp: [
			"#F5F3FF",
			"#EDE9FE",
			"#DDD6FE",
			"#C4B5FD",
			"#A78BFA",
			"#8B5CF6",
			"#7C3AED",
			"#6D28D9",
			"#5B21B6",
			"#4C1D95",
		],
	},
	red: {
		id: "red",
		label: "Red",
		ramp: [
			"#FEF2F2",
			"#FEE2E2",
			"#FECACA",
			"#FCA5A5",
			"#F87171",
			"#EF4444",
			"#DC2626",
			"#B91C1C",
			"#991B1B",
			"#7F1D1D",
		],
	},
	amber: {
		id: "amber",
		label: "Amber",
		ramp: [
			"#FFFBEB",
			"#FEF3C7",
			"#FDE68A",
			"#FCD34D",
			"#FBBF24",
			"#F59E0B",
			"#D97706",
			"#B45309",
			"#92400E",
			"#78350F",
		],
	},
	teal: {
		id: "teal",
		label: "Teal",
		ramp: [
			"#F0FDFA",
			"#CCFBF1",
			"#99F6E4",
			"#5EEAD4",
			"#2DD4BF",
			"#14B8A6",
			"#0D9488",
			"#0F766E",
			"#115E59",
			"#134E4A",
		],
	},
}

const SHADE_STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

const GRAY_LIGHT = [
	"#F8F8F8",
	"#F3F3F3",
	"#EDEDED",
	"#E2E2E2",
	"#C7C7C7",
	"#999999",
	"#7C7C7C",
	"#525252",
	"#383838",
	"#171717",
]

const GRAY_DARK = [
	"#171717",
	"#232323",
	"#2E2E2E",
	"#3F3F3F",
	"#8A8A8A",
	"#A1A1A1",
	"#C4C4C4",
	"#D4D4D4",
	"#E4E4E4",
	"#F4F4F4",
]

const WHITE_LIGHT = "#FFFFFF"
const WHITE_DARK = "#242428"

/** Supporting colour ramps remapped for dark mode contrast */
const SUPPORT_RAMPS = {
	red: [
		"#FEF2F2",
		"#FEE2E2",
		"#FECACA",
		"#FCA5A5",
		"#F87171",
		"#EF4444",
		"#DC2626",
		"#B91C1C",
		"#991B1B",
		"#7F1D1D",
	],
	green: [
		"#F0FDF4",
		"#DCFCE7",
		"#BBF7D0",
		"#86EFAC",
		"#4ADE80",
		"#22C55E",
		"#16A34A",
		"#15803D",
		"#166534",
		"#14532D",
	],
	orange: [
		"#FFF7ED",
		"#FFEDD5",
		"#FED7AA",
		"#FDBA74",
		"#FB923C",
		"#F97316",
		"#EA580C",
		"#C2410C",
		"#9A3412",
		"#7C2D12",
	],
	amber: [
		"#FFFBEB",
		"#FEF3C7",
		"#FDE68A",
		"#FCD34D",
		"#FBBF24",
		"#F59E0B",
		"#D97706",
		"#B45309",
		"#92400E",
		"#78350F",
	],
	purple: [
		"#FAF5FF",
		"#F3E8FF",
		"#E9D5FF",
		"#D8B4FE",
		"#C084FC",
		"#A855F7",
		"#9333EA",
		"#7E22CE",
		"#6B21A8",
		"#581C87",
	],
	emerald: [
		"#ECFDF5",
		"#D1FAE5",
		"#A7F3D0",
		"#6EE7B7",
		"#34D399",
		"#10B981",
		"#059669",
		"#047857",
		"#065F46",
		"#064E3B",
	],
	yellow: [
		"#FEFCE8",
		"#FEF9C3",
		"#FEF08A",
		"#FDE047",
		"#FACC15",
		"#EAB308",
		"#CA8A04",
		"#A16207",
		"#854D0E",
		"#713F12",
	],
	indigo: [
		"#EEF2FF",
		"#E0E7FF",
		"#C7D2FE",
		"#A5B4FC",
		"#818CF8",
		"#6366F1",
		"#4F46E5",
		"#4338CA",
		"#3730A3",
		"#312E81",
	],
	teal: [
		"#F0FDFA",
		"#CCFBF1",
		"#99F6E4",
		"#5EEAD4",
		"#2DD4BF",
		"#14B8A6",
		"#0D9488",
		"#0F766E",
		"#115E59",
		"#134E4A",
	],
	violet: [
		"#F5F3FF",
		"#EDE9FE",
		"#DDD6FE",
		"#C4B5FD",
		"#A78BFA",
		"#8B5CF6",
		"#7C3AED",
		"#6D28D9",
		"#5B21B6",
		"#4C1D95",
	],
	pink: [
		"#FDF2F8",
		"#FCE7F3",
		"#FBCFE8",
		"#F9A8D4",
		"#F472B6",
		"#EC4899",
		"#DB2777",
		"#BE185D",
		"#9D174D",
		"#831843",
	],
	cyan: [
		"#ECFEFF",
		"#CFFAFE",
		"#A5F3FC",
		"#67E8F9",
		"#22D3EE",
		"#06B6D4",
		"#0891B2",
		"#0E7490",
		"#155E75",
		"#164E63",
	],
}

function hexToRgbChannels(hex) {
	const raw = hex.replace("#", "")
	return [
		Number.parseInt(raw.slice(0, 2), 16),
		Number.parseInt(raw.slice(2, 4), 16),
		Number.parseInt(raw.slice(4, 6), 16),
	]
}

const toChannels = (hex) => hexToRgbChannels(hex).join(" ")

function mixChannels(fromHex, toHex, amount) {
	const from = hexToRgbChannels(fromHex)
	const to = hexToRgbChannels(toHex)
	return from
		.map((channel, index) => Math.round(channel + (to[index] - channel) * amount))
		.join(" ")
}

/** Dark-mode accent ramp: blend main colour toward near-black for soft surfaces */
function darkenRamp(ramp) {
	const base = GRAY_DARK[0]
	const main = ramp[5]
	return [
		mixChannels(main, base, 0.88),
		mixChannels(main, base, 0.8),
		mixChannels(main, base, 0.66),
		mixChannels(main, base, 0.46),
		mixChannels(main, base, 0.24),
		toChannels(main),
		toChannels(ramp[4]),
		toChannels(ramp[3]),
		toChannels(ramp[2]),
		toChannels(ramp[1]),
	]
}

export function getStoredAccent() {
	try {
		const value = localStorage.getItem(ACCENT_STORAGE_KEY)
		if (value && ACCENT_SCALES[value]) return value
	} catch {
		/* ignore */
	}
	return "blue"
}

export function getStoredThemeMode() {
	try {
		const value = localStorage.getItem(THEME_MODE_STORAGE_KEY)
		if (value === "dark" || value === "light") return value
	} catch {
		/* ignore */
	}
	return "light"
}

/**
 * Apply accent + display mode to <html> CSS variables and data attributes.
 */
export function applyTheme(accentId = getStoredAccent(), themeMode = getStoredThemeMode()) {
	const accent = ACCENT_SCALES[accentId] || ACCENT_SCALES.blue
	const isDark = themeMode === "dark"
	const root = document.documentElement
	const grayRamp = isDark ? GRAY_DARK : GRAY_LIGHT
	const blueRamp = isDark ? darkenRamp(accent.ramp) : accent.ramp.map(toChannels)

	SHADE_STEPS.forEach((step, index) => {
		root.style.setProperty(`--c-blue-${step}`, blueRamp[index])
		root.style.setProperty(`--c-gray-${step}`, toChannels(grayRamp[index]))
	})

	for (const [name, ramp] of Object.entries(SUPPORT_RAMPS)) {
		const channels = isDark ? darkenRamp(ramp) : ramp.map(toChannels)
		SHADE_STEPS.forEach((step, index) => {
			root.style.setProperty(`--c-${name}-${step}`, channels[index])
		})
	}

	root.style.setProperty("--c-white", toChannels(isDark ? WHITE_DARK : WHITE_LIGHT))
	root.setAttribute("data-theme", themeMode)
	root.setAttribute("data-accent", accent.id)
	root.style.colorScheme = isDark ? "dark" : "light"
}

export function setAccent(accentId) {
	if (!ACCENT_SCALES[accentId]) return
	try {
		localStorage.setItem(ACCENT_STORAGE_KEY, accentId)
	} catch {
		/* ignore */
	}
	applyTheme(accentId, getStoredThemeMode())
}

export function setThemeMode(mode) {
	const themeMode = mode === "dark" ? "dark" : "light"
	try {
		localStorage.setItem(THEME_MODE_STORAGE_KEY, themeMode)
	} catch {
		/* ignore */
	}
	applyTheme(getStoredAccent(), themeMode)
}

export function getAccentList() {
	return Object.values(ACCENT_SCALES)
}

/** Swatch preview chips for the Appearance panel */
export function getAccentPreview(accent) {
	return [
		{ label: "Light", hex: accent.ramp[0], fg: "#1F2937" },
		{ label: "Main", hex: accent.ramp[5], fg: "#FFFFFF" },
		{ label: "Dark", hex: accent.ramp[9], fg: "#FFFFFF" },
	]
}

/** Call once at app boot (before mount) */
export function initTheme() {
	applyTheme()
}
