import frappeUIPreset from "frappe-ui/src/tailwind/preset"

/** CSS-variable colour scale used by the Appearance theme engine */
function cssVarScale(name) {
	return {
		50: `rgb(var(--c-${name}-50) / <alpha-value>)`,
		100: `rgb(var(--c-${name}-100) / <alpha-value>)`,
		200: `rgb(var(--c-${name}-200) / <alpha-value>)`,
		300: `rgb(var(--c-${name}-300) / <alpha-value>)`,
		400: `rgb(var(--c-${name}-400) / <alpha-value>)`,
		500: `rgb(var(--c-${name}-500) / <alpha-value>)`,
		600: `rgb(var(--c-${name}-600) / <alpha-value>)`,
		700: `rgb(var(--c-${name}-700) / <alpha-value>)`,
		800: `rgb(var(--c-${name}-800) / <alpha-value>)`,
		900: `rgb(var(--c-${name}-900) / <alpha-value>)`,
	}
}

export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				// Runtime-themed scales (see src/utils/theme.js)
				blue: cssVarScale("blue"),
				gray: cssVarScale("gray"),
				red: cssVarScale("red"),
				green: cssVarScale("green"),
				orange: cssVarScale("orange"),
				amber: cssVarScale("amber"),
				purple: cssVarScale("purple"),
				emerald: cssVarScale("emerald"),
				yellow: cssVarScale("yellow"),
				indigo: cssVarScale("indigo"),
				teal: cssVarScale("teal"),
				violet: cssVarScale("violet"),
				pink: cssVarScale("pink"),
				cyan: cssVarScale("cyan"),
				white: "rgb(var(--c-white) / <alpha-value>)",
			},
		},
	},
	plugins: [],
}
