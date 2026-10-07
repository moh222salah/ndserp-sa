<template>
	<div ref="rootEl" class="relative">
		<button
			type="button"
			class="relative p-1 sm:p-2 rounded-lg text-gray-600 hover:text-blue-600 hover:bg-blue-50 transition-colors touch-manipulation focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
			:title="__('Appearance')"
			:aria-label="__('Appearance')"
			:aria-expanded="open"
			@click="open = !open"
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M7 21a4 4 0 01-4-4 4 4 0 014-4h1.5M7 21h10a4 4 0 004-4c0-6.075-4.925-11-11-11a7 7 0 00-7 7"
				/>
				<circle cx="10.5" cy="8.5" r="1.4" fill="currentColor" stroke="none" />
				<circle cx="15" cy="11" r="1.4" fill="currentColor" stroke="none" />
				<circle cx="15.5" cy="15.5" r="1.4" fill="currentColor" stroke="none" />
			</svg>
			<span
				class="absolute bottom-0.5 end-0.5 w-2 h-2 rounded-full border border-white bg-blue-500"
			/>
		</button>

		<Transition
			enter-active-class="transition duration-150 ease-out"
			enter-from-class="opacity-0 -translate-y-1 scale-95"
			enter-to-class="opacity-100 translate-y-0 scale-100"
			leave-active-class="transition duration-100 ease-in"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0 scale-95"
		>
			<div
				v-if="open"
				class="absolute top-full mt-2 end-0 z-[10000] w-[19rem] max-w-[92vw] rounded-xl border border-gray-200 bg-white shadow-xl overflow-hidden"
			>
				<div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
					<h3 class="text-sm font-bold text-gray-900">{{ __("Appearance") }}</h3>
					<p class="text-[11px] text-gray-500 mt-0.5">
						{{ __("Choose a colour palette and display mode") }}
					</p>
				</div>

				<div class="px-4 py-3 border-b border-gray-200">
					<p class="text-[11px] font-bold text-gray-500 uppercase tracking-wide mb-2">
						{{ __("Display Mode") }}
					</p>
					<div class="grid grid-cols-2 gap-2">
						<button
							v-for="mode in displayModes"
							:key="mode.id"
							type="button"
							class="flex items-center justify-center gap-2 px-3 py-2 rounded-lg border-2 text-xs font-bold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
							:class="
								themeMode === mode.id
									? 'bg-blue-600 text-white border-blue-600'
									: 'bg-white text-gray-700 border-gray-200 hover:border-blue-300 hover:text-blue-600'
							"
							@click="selectMode(mode.id)"
						>
							<svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" :d="mode.icon" />
							</svg>
							{{ __(mode.label) }}
						</button>
					</div>
				</div>

				<div class="px-4 py-3">
					<p class="text-[11px] font-bold text-gray-500 uppercase tracking-wide mb-2">
						{{ __("Colour Palette") }}
					</p>
					<div class="space-y-2">
						<button
							v-for="accent in accents"
							:key="accent.id"
							type="button"
							class="w-full rounded-lg border-2 overflow-hidden transition-colors text-start focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
							:class="
								currentAccent === accent.id
									? 'border-blue-600'
									: 'border-gray-200 hover:border-gray-300'
							"
							@click="selectAccent(accent.id)"
						>
							<div class="flex items-center justify-between px-2.5 pt-2 pb-1.5">
								<span class="text-xs font-bold text-gray-900">{{ __(accent.label) }}</span>
								<svg
									v-if="currentAccent === accent.id"
									class="w-4 h-4 text-blue-600"
									viewBox="0 0 20 20"
									fill="currentColor"
								>
									<path
										fill-rule="evenodd"
										d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 111.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z"
										clip-rule="evenodd"
									/>
								</svg>
							</div>
							<div class="grid grid-cols-3">
								<div
									v-for="chip in getAccentPreview(accent)"
									:key="chip.label"
									class="py-2 text-center"
									:style="{ backgroundColor: chip.hex, color: chip.fg }"
								>
									<div class="text-[9px] font-bold leading-none">{{ __(chip.label) }}</div>
									<div class="text-[9px] font-bold mt-1 leading-none opacity-90">
										{{ chip.hex.toUpperCase() }}
									</div>
								</div>
							</div>
						</button>
					</div>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from "vue"
import {
	getAccentList,
	getAccentPreview,
	getStoredAccent,
	getStoredThemeMode,
	setAccent,
	setThemeMode,
} from "@/utils/theme"

const open = ref(false)
const rootEl = ref(null)
const currentAccent = ref(getStoredAccent())
const themeMode = ref(getStoredThemeMode())
const accents = getAccentList()

const displayModes = [
	{
		id: "light",
		label: "Light",
		icon: "M12 3v1m0 16v1m9-9h-1M4 12H3m15.4-6.4l-.7.7M6.3 17.7l-.7.7m12.8 0l-.7-.7M6.3 6.3l-.7-.7M16 12a4 4 0 11-8 0 4 4 0 018 0z",
	},
	{
		id: "dark",
		label: "Dark",
		icon: "M20.4 14.9A8 8 0 019.1 3.6a8 8 0 1011.3 11.3z",
	},
]

function selectAccent(id) {
	setAccent(id)
	currentAccent.value = id
}

function selectMode(id) {
	setThemeMode(id)
	themeMode.value = id
}

function onDocumentClick(event) {
	if (open.value && rootEl.value && !rootEl.value.contains(event.target)) {
		open.value = false
	}
}

function onKeydown(event) {
	if (event.key === "Escape") open.value = false
}

onMounted(() => {
	document.addEventListener("click", onDocumentClick)
	document.addEventListener("keydown", onKeydown)
})

onBeforeUnmount(() => {
	document.removeEventListener("click", onDocumentClick)
	document.removeEventListener("keydown", onKeydown)
})
</script>
