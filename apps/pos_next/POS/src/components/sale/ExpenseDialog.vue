<template>
	<Dialog v-model="show" :options="{ title: __('Record Expense'), size: 'md' }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<!-- Account info -->
				<div v-if="dialogDataResource.data" class="bg-amber-50 border border-amber-200 rounded-lg p-3">
					<div class="flex items-start gap-2">
						<svg class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd"
								d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
								clip-rule="evenodd" />
						</svg>
						<div class="flex-1 text-xs text-amber-900">
							<p class="font-semibold">{{ __('Cash expense from drawer') }}</p>
							<p class="mt-1 text-amber-800">
								{{ __('Debit') }}: {{ selectedExpenseAccountLabel }}
							</p>
							<p class="text-amber-800">
								{{ __('Credit') }}: {{ dialogDataResource.data.cash_account_label }}
								<span class="text-amber-700">({{ dialogDataResource.data.cash_mode_of_payment }})</span>
							</p>
						</div>
					</div>
				</div>

				<div v-if="dialogDataResource.loading" class="text-center py-4">
					<div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
				</div>

				<template v-else-if="dialogDataResource.data">
					<!-- Expense account -->
					<div v-if="expenseAccountOptions.length">
						<label class="block text-sm font-medium text-gray-700 mb-2 text-start">
							{{ __('Expense Account') }}
						</label>
						<select
							v-model="selectedExpenseAccount"
							class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
							:disabled="submitting"
						>
							<option
								v-for="account in expenseAccountOptions"
								:key="account.name"
								:value="account.name"
							>
								{{ account.account_name || account.name }}
							</option>
						</select>
					</div>

					<!-- Amount input & keypad -->
					<div class="flex flex-col" @keydown="handleAmountKeydown">
						<label class="block text-sm font-medium text-gray-700 mb-2 text-start">
							{{ __('Amount') }}
						</label>
						<div class="bg-gray-100 rounded-xl px-4 py-4 mb-3 text-end focus-within:ring-2 focus-within:ring-blue-400 focus-within:bg-white transition-colors">
							<input
								ref="amountInputRef"
								type="text"
								inputmode="decimal"
								:value="amountInput"
								@input="handleAmountInputChange"
								@keydown.enter.prevent="submitExpense"
								@keydown.escape.prevent="handleClear"
								:disabled="submitting"
								class="w-full bg-transparent text-2xl font-bold text-gray-900 font-mono tracking-wide text-end border-none outline-none placeholder:text-gray-400 disabled:text-gray-500"
								:placeholder="__('0.00')"
								:aria-label="__('Expense amount')"
							/>
						</div>

						<PaymentKeypad
							:disabled="!canSubmit"
							:submit-label="__('Record')"
							@key-press="handleKeyPress"
							@backspace="handleBackspace"
							@clear="handleClear"
							@add="submitExpense"
						/>
					</div>

					<!-- Notes -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2 text-start">
							{{ __('Notes') }}
						</label>
						<textarea
							v-model="notes"
							rows="3"
							:placeholder="__('Describe the expense (optional)')"
							class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
							:disabled="submitting"
						/>
					</div>
				</template>

				<div v-if="dialogDataResource.error" class="rounded-md bg-red-50 p-4">
					<p class="text-sm text-red-800">{{ formatResourceError(dialogDataResource.error) }}</p>
				</div>

				<div v-if="errorMessage" class="rounded-md bg-red-50 p-4">
					<p class="text-sm text-red-800">{{ errorMessage }}</p>
				</div>

				<div v-if="successMessage" class="rounded-md bg-green-50 border border-green-200 p-4">
					<p class="text-sm text-green-800 font-medium">{{ successMessage }}</p>
				</div>
			</div>
		</template>

		<template #actions>
			<div class="flex justify-end gap-2 w-full">
				<Button variant="subtle" @click="show = false" :disabled="submitting">
					{{ successMessage ? __('Close') : __('Cancel') }}
				</Button>
				<Button
					v-if="!successMessage"
					theme="blue"
					variant="solid"
					:loading="submitting"
					:disabled="!canSubmit"
					@click="submitExpense"
				>
					{{ __('Record Expense') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import PaymentKeypad from "@/components/sale/PaymentKeypad.vue"
import { Button, Dialog, call, createResource } from "frappe-ui"
import { computed, nextTick, ref, watch } from "vue"

const props = defineProps({
	modelValue: {
		type: Boolean,
		default: false,
	},
	posProfile: {
		type: String,
		default: "",
	},
	posOpeningShift: {
		type: String,
		default: "",
	},
	currency: {
		type: String,
		default: "USD",
	},
})

const emit = defineEmits(["update:modelValue", "expense-recorded"])

const show = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
})

const amountInput = ref("")
const amountInputRef = ref(null)
const notes = ref("")
const selectedExpenseAccount = ref("")
const submitting = ref(false)
const errorMessage = ref("")
const successMessage = ref("")

const dialogDataResource = createResource({
	url: "pos_next.api.expenses.get_expense_dialog_data",
	auto: false,
	onSuccess(data) {
		selectedExpenseAccount.value = data?.expense_account || ""
	},
})

const expenseAccountOptions = computed(
	() => dialogDataResource.data?.expense_accounts || [],
)

const selectedExpenseAccountLabel = computed(() => {
	const selected = expenseAccountOptions.value.find(
		(account) => account.name === selectedExpenseAccount.value,
	)
	return (
		selected?.account_name ||
		dialogDataResource.data?.expense_account_label ||
		selectedExpenseAccount.value
	)
})

const canSubmit = computed(() => {
	const value = parseFloat(amountInput.value)
	return (
		value > 0 &&
		!submitting.value &&
		dialogDataResource.data &&
		!!selectedExpenseAccount.value
	)
})

function formatResourceError(error) {
	if (!error) return ""
	if (typeof error === "string") return error
	return (
		error?.messages?.[0] ||
		error?.message ||
		error?.exc_type ||
		__("Failed to load expense accounts")
	)
}

function sanitizeAmountValue(value) {
	let sanitized = String(value || "").replace(/[^\d.]/g, "")
	const dotIndex = sanitized.indexOf(".")
	if (dotIndex !== -1) {
		sanitized =
			sanitized.slice(0, dotIndex + 1) +
			sanitized.slice(dotIndex + 1).replace(/\./g, "")
	}
	const parts = sanitized.split(".")
	if (parts[1]?.length > 2) {
		sanitized = `${parts[0]}.${parts[1].slice(0, 2)}`
	}
	return sanitized
}

function handleAmountInputChange(event) {
	amountInput.value = sanitizeAmountValue(event.target.value)
	errorMessage.value = ""
}

function handleAmountKeydown(event) {
	const target = event.target

	if (target === amountInputRef.value) return

	if (
		target.tagName === "INPUT" ||
		target.tagName === "TEXTAREA" ||
		target.tagName === "SELECT" ||
		target.isContentEditable
	) {
		return
	}

	if (event.key === "Enter") {
		event.preventDefault()
		submitExpense()
		return
	}
	if (event.key === "Backspace") {
		event.preventDefault()
		handleBackspace()
		return
	}
	if (event.key === "Escape") {
		event.preventDefault()
		handleClear()
		return
	}

	if (/^\d$/.test(event.key)) {
		event.preventDefault()
		handleKeyPress(event.key)
		return
	}
	if (event.key === ".") {
		event.preventDefault()
		handleKeyPress(".")
	}
}

function resetForm() {
	amountInput.value = ""
	notes.value = ""
	selectedExpenseAccount.value = dialogDataResource.data?.expense_account || ""
	errorMessage.value = ""
	successMessage.value = ""
	submitting.value = false
}

function loadDialogData() {
	if (!props.posProfile) return
	dialogDataResource.submit({ pos_profile: props.posProfile })
}

watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) {
			resetForm()
			loadDialogData()
			nextTick(() => amountInputRef.value?.focus())
		}
	},
)

watch(
	() => props.posProfile,
	() => {
		if (props.modelValue) {
			loadDialogData()
		}
	},
)

function handleKeyPress(key) {
	errorMessage.value = ""

	if (key === ".") {
		if (!amountInput.value.includes(".")) {
			amountInput.value = amountInput.value ? `${amountInput.value}.` : "0."
		}
		nextTick(() => amountInputRef.value?.focus())
		return
	}

	if (key === "00") {
		amountInput.value = amountInput.value ? `${amountInput.value}00` : "0"
		nextTick(() => amountInputRef.value?.focus())
		return
	}

	if (amountInput.value === "0" && key !== ".") {
		amountInput.value = key
	} else {
		amountInput.value = `${amountInput.value || ""}${key}`
	}

	nextTick(() => amountInputRef.value?.focus())
}

function handleBackspace() {
	amountInput.value = amountInput.value.slice(0, -1)
}

function handleClear() {
	amountInput.value = ""
}

async function submitExpense() {
	const amount = parseFloat(amountInput.value)
	if (!amount || amount <= 0) {
		errorMessage.value = __("Expense amount must be greater than zero")
		return
	}

	if (!canSubmit.value) return

	submitting.value = true
	errorMessage.value = ""

	try {
		const response = await call("pos_next.api.expenses.create_pos_expense", {
			pos_profile: props.posProfile,
			amount,
			notes: notes.value.trim(),
			pos_opening_shift: props.posOpeningShift || undefined,
			expense_account: selectedExpenseAccount.value || undefined,
		})

		successMessage.value = response.message || __("Expense recorded successfully")
		emit("expense-recorded", response)
		amountInput.value = ""
		notes.value = ""
	} catch (error) {
		errorMessage.value =
			error?.message || error?.messages?.[0] || __("Failed to record expense")
	} finally {
		submitting.value = false
	}
}
</script>
