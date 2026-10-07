<template>
	<div class="flex gap-2">
		<!-- Numeric grid -->
		<div class="flex-1 grid grid-cols-3 gap-2">
			<button
				v-for="key in numberKeys"
				:key="key"
				type="button"
				@click="pressKey(key)"
				class="h-12 rounded-xl bg-white border border-gray-200 text-lg font-semibold text-gray-800 hover:bg-gray-50 active:bg-gray-100 transition-colors touch-manipulation"
			>
				{{ key }}
			</button>
		</div>

		<!-- Action column -->
		<div class="flex flex-col gap-2 w-16">
			<button
				type="button"
				@click="$emit('backspace')"
				class="h-12 rounded-xl bg-white border border-gray-200 flex items-center justify-center text-red-500 hover:bg-red-50 active:bg-red-100 transition-colors touch-manipulation"
				:aria-label="__('Backspace')"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l3.5-3.5M3 12l3.5 3.5"/>
				</svg>
			</button>
			<button
				type="button"
				@click="$emit('clear')"
				class="h-12 rounded-xl bg-white border border-gray-200 text-lg font-bold text-orange-500 hover:bg-orange-50 active:bg-orange-100 transition-colors touch-manipulation"
			>
				C
			</button>
			<button
				type="button"
				@click="$emit('add')"
				:disabled="disabled"
				:class="[
					'flex-1 min-h-[6.5rem] rounded-xl text-sm font-bold transition-colors touch-manipulation',
					disabled
						? 'bg-gray-100 text-gray-400 cursor-not-allowed'
						: 'bg-[#7AB2E1] text-white hover:bg-[#6aa3d4] active:bg-[#5a94c5]'
				]"
			>
				{{ submitLabel || __('Add') }}
			</button>
		</div>
	</div>
</template>

<script setup>
defineProps({
	disabled: {
		type: Boolean,
		default: false,
	},
	submitLabel: {
		type: String,
		default: "",
	},
})

const emit = defineEmits(["key-press", "backspace", "clear", "add"])

const numberKeys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "."]

function pressKey(key) {
	emit("key-press", key)
}
</script>
