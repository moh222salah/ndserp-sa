<template>
	<Dialog v-model="show" :options="{ title: __('Complete Payment'), size: '5xl' }">
		<template #body-content>
			<div class="flex flex-col lg:flex-row gap-0 min-h-[480px] -mx-1">
				<!-- LEFT COLUMN: Invoice Summary (~35%) -->
				<div class="lg:w-[35%] flex flex-col bg-gray-50 border-b lg:border-b-0 lg:border-e border-gray-200">
					<!-- Outstanding Balance Bar -->
					<div
						v-if="allowCreditSale && totalAvailableCredit < 0"
						class="bg-red-50 px-4 py-3 flex items-center justify-between border-b border-red-100"
					>
						<span class="text-sm font-semibold text-red-600">{{ __('Outstanding Balance') }}</span>
						<span class="text-lg font-bold text-red-600">{{ formatCurrency(Math.abs(totalAvailableCredit)) }}</span>
					</div>

					<!-- Invoice Summary Header -->
					<div class="px-4 pt-4 pb-2">
						<div class="flex items-center justify-between mb-1">
							<h3 class="text-base font-bold text-gray-900">{{ __('Invoice Summary') }}</h3>
							<span class="text-xs text-gray-500 font-medium">{{ itemCountLabel }}</span>
						</div>
						<p class="text-sm text-gray-500">{{ customerDisplayName }}</p>
					</div>

					<!-- Offers & Coupon Buttons -->
					<div v-if="items.length > 0" class="px-4 pb-3 flex gap-2">
						<button
							type="button"
							@click="$emit('show-offers')"
							class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-white border-2 border-green-300 text-green-700 hover:bg-green-50 transition-colors touch-manipulation"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z"/>
							</svg>
							<span class="text-xs font-bold">{{ __('Offers') }}</span>
						</button>
						<button
							type="button"
							@click="$emit('show-coupons')"
							class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-white border-2 border-purple-300 text-purple-700 hover:bg-purple-50 transition-colors touch-manipulation"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z"/>
							</svg>
							<span class="text-xs font-bold">{{ __('Coupon') }}</span>
						</button>
					</div>

					<!-- Item List -->
					<div class="flex-1 overflow-y-auto px-4 min-h-[120px] max-h-[220px] lg:max-h-none">
						<div v-if="items.length === 0" class="py-6 text-center text-sm text-gray-400">
							{{ __('No items') }}
						</div>
						<div v-else class="flex flex-col gap-3">
							<div
								v-for="(item, index) in items"
								:key="index"
								class="flex items-start justify-between gap-2"
							>
								<div class="min-w-0 flex-1">
									<p class="text-sm font-semibold text-gray-900 truncate">{{ item.item_name }}</p>
									<p class="text-xs text-gray-500">
										{{ formatCurrency(item.rate || item.price_list_rate || 0) }}
										<span class="mx-1">×</span>
										{{ item.quantity }}
									</p>
								</div>
								<span class="text-sm font-semibold text-gray-900 flex-shrink-0">
									{{ formatCurrency(getItemTotal(item)) }}
								</span>
							</div>
						</div>
					</div>

					<!-- Totals -->
					<div class="px-4 py-3 border-t border-gray-200 space-y-1.5">
						<div class="flex justify-between text-sm text-gray-600">
							<span>{{ __('Subtotal') }}</span>
							<span>{{ formatCurrency(subtotal) }}</span>
						</div>
						<div v-if="discountAmount > 0" class="flex justify-between text-sm text-red-600">
							<span>{{ __('Discount') }}</span>
							<span>-{{ formatCurrency(discountAmount) }}</span>
						</div>
						<div v-if="taxAmount > 0" class="flex justify-between text-sm text-gray-600">
							<span>{{ __('Tax') }}</span>
							<span>{{ formatCurrency(taxAmount) }}</span>
						</div>
						<div class="flex justify-between items-center pt-1">
							<span class="text-sm font-semibold text-gray-700">{{ __('Grand Total') }}</span>
							<span class="text-xl font-bold text-gray-900">{{ formatCurrency(grandTotal) }}</span>
						</div>
					</div>

					<!-- Payment Breakdown (compact) -->
					<div v-if="paymentEntries.length > 0" class="px-4 pb-2">
						<div
							v-for="(entry, index) in paymentEntries"
							:key="index"
							class="group flex items-center justify-between py-1.5 text-sm"
						>
							<div class="flex items-center gap-2 min-w-0">
								<span>{{ getPaymentIcon(entry.type) }}</span>
								<span class="text-gray-700 truncate">{{ entry.mode_of_payment }}</span>
							</div>
							<div class="flex items-center gap-2">
								<span class="font-semibold text-gray-900">{{ formatCurrency(entry.amount) }}</span>
								<button
									@click="removePaymentEntry(index)"
									class="opacity-0 group-hover:opacity-100 p-0.5 text-red-500 hover:text-red-700 transition-opacity"
								>
									<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
									</svg>
								</button>
							</div>
						</div>
						<div v-if="changeAmount > 0" class="flex justify-between text-sm text-green-600 py-1">
							<span>{{ __('Change') }}</span>
							<span class="font-semibold">{{ formatCurrency(changeAmount) }}</span>
						</div>
					</div>

					<!-- PAID / REMAINING Cards -->
					<div class="grid grid-cols-2 gap-2 px-4 pb-4 pt-2">
						<div class="bg-blue-50 rounded-xl p-3 text-center border border-blue-100">
							<div class="text-[10px] font-bold text-blue-600 uppercase tracking-wide mb-1">{{ __('Paid') }}</div>
							<div class="text-lg font-bold text-blue-700">{{ formatCurrency(totalPaid) }}</div>
						</div>
						<div class="bg-orange-50 rounded-xl p-3 text-center border border-orange-100">
							<div class="text-[10px] font-bold text-orange-600 uppercase tracking-wide mb-1">{{ __('Remaining') }}</div>
							<div class="text-lg font-bold text-orange-600">{{ formatCurrency(remainingAmount) }}</div>
						</div>
					</div>
				</div>

				<!-- RIGHT COLUMN: Payment Interface (~65%) -->
				<div class="lg:w-[65%] flex flex-col p-4 gap-4">
					<!-- Payment Methods -->
					<div>
						<div class="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">
							{{ __('Payment Method') }}
						</div>
						<div v-if="loadingPaymentMethods" class="flex items-center justify-center py-6">
							<div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
							<span class="ms-2 text-sm text-gray-500">{{ __('Loading payment methods...') }}</span>
						</div>
						<div v-else-if="paymentMethods.length > 0" class="flex flex-wrap gap-2">
							<button
								v-for="method in paymentMethods"
								:key="method.mode_of_payment"
								type="button"
								@click="selectPaymentMethod(method)"
								:class="[
									'flex flex-col items-center justify-center gap-1 px-4 py-2.5 rounded-xl border-2 min-w-[80px] transition-all touch-manipulation',
									lastSelectedMethod?.mode_of_payment === method.mode_of_payment
										? 'border-blue-400 bg-blue-50 shadow-sm'
										: 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
								]"
							>
								<span class="text-xl">{{ getPaymentIcon(method.type) }}</span>
								<span class="text-[11px] font-semibold text-gray-800 text-center leading-tight">
									{{ method.mode_of_payment }}
								</span>
								<span
									v-if="getMethodTotal(method.mode_of_payment) > 0"
									class="text-[10px] font-bold text-blue-600"
								>
									{{ formatCurrency(getMethodTotal(method.mode_of_payment)) }}
								</span>
							</button>
						</div>
						<div v-else class="text-center py-4 text-sm text-gray-500">
							{{ __('No payment methods available') }}
						</div>
					</div>

					<!-- Redeem Points / Apply Credit -->
					<button
						v-if="allowCreditSale && totalAvailableCredit > 0 && remainingAmount > 0"
						type="button"
						@click="applyCustomerCredit"
						class="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-gray-100 hover:bg-gray-200 transition-colors touch-manipulation"
					>
						<div class="flex items-center gap-2">
							<svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"/>
							</svg>
							<span class="text-sm font-medium text-gray-700">{{ __('Redeem Points') }}</span>
						</div>
						<span class="text-sm font-bold text-gray-800">{{ formatCurrency(totalAvailableCredit) }}</span>
					</button>

					<!-- Customer Credit Available (positive balance info) -->
					<div
						v-else-if="allowCreditSale && totalAvailableCredit > 0"
						class="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-emerald-50 border border-emerald-200"
					>
						<span class="text-sm font-medium text-emerald-700">{{ __('Customer Credit Available') }}</span>
						<span class="text-sm font-bold text-emerald-700">{{ formatCurrency(totalAvailableCredit) }}</span>
					</div>

					<!-- Quick Amounts -->
					<div v-if="remainingAmount > 0 && lastSelectedMethod">
						<div class="text-xs font-medium text-gray-500 mb-2">
							{{ __('Quick amounts for {0}', [lastSelectedMethod.mode_of_payment]) }}
						</div>
						<div class="grid grid-cols-4 gap-2">
							<button
								v-for="amount in quickAmounts"
								:key="amount"
								type="button"
								@click="addCustomPayment(lastSelectedMethod, amount)"
								class="px-2 py-2.5 text-sm font-semibold rounded-xl bg-white border border-gray-200 hover:border-blue-400 hover:bg-blue-50 text-gray-700 transition-all touch-manipulation"
							>
								{{ formatCurrency(amount) }}
							</button>
						</div>
					</div>

					<!-- Amount Display & Keypad -->
					<div
						v-if="remainingAmount > 0 && lastSelectedMethod"
						class="flex-1 flex flex-col"
						@keydown="handlePaymentKeydown"
					>
						<div class="bg-gray-100 rounded-xl px-4 py-4 mb-3 text-end focus-within:ring-2 focus-within:ring-blue-400 focus-within:bg-white transition-colors">
							<input
								ref="keypadInputRef"
								type="text"
								inputmode="decimal"
								:value="keypadInput"
								@input="handleKeypadInputChange"
								@keydown.enter.prevent="handleKeypadAdd"
								@keydown.escape.prevent="handleClearKeypad"
								class="w-full bg-transparent text-2xl font-bold text-gray-900 font-mono tracking-wide text-end border-none outline-none placeholder:text-gray-400"
								:placeholder="__('0.00')"
								:aria-label="__('Payment amount')"
							/>
						</div>
						<PaymentKeypad
							:disabled="!keypadAmount || keypadAmount <= 0"
							@key-press="handleKeyPress"
							@backspace="handleBackspace"
							@clear="handleClearKeypad"
							@add="handleKeypadAdd"
						/>
					</div>
					<div v-else-if="remainingAmount === 0 && paymentEntries.length > 0" class="flex-1 flex items-center justify-center">
						<div class="flex items-center gap-2 text-green-600">
							<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
							</svg>
							<span class="text-lg font-semibold">{{ __('Paid in Full') }}</span>
						</div>
					</div>
					<div v-else-if="!lastSelectedMethod && paymentMethods.length > 0" class="flex-1 flex items-center justify-center text-sm text-gray-400">
						{{ __('Select a payment method') }}
					</div>

					<!-- Collapsible: Sales Persons -->
					<details v-if="settingsStore.enableSalesPersons" class="group">
						<summary class="text-xs font-semibold text-purple-700 cursor-pointer hover:text-purple-900 list-none flex items-center gap-1">
							<svg class="w-3 h-3 transition-transform group-open:rotate-90" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
							</svg>
							{{ settingsStore.isMultipleSalesPersons ? __('Sales Persons') : __('Sales Person') }}
							<span v-if="selectedSalesPersons.length > 0" class="text-purple-500">({{ selectedSalesPersons.length }})</span>
						</summary>
						<div class="mt-2 bg-purple-50 border border-purple-200 rounded-lg p-3 space-y-2">
							<div class="relative">
								<input
									v-model="salesPersonSearch"
									type="text"
									:placeholder="__('Search sales person...')"
									class="w-full px-3 py-2 ps-8 text-xs border border-purple-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white"
								/>
								<svg class="w-4 h-4 text-gray-400 absolute start-2.5 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
								</svg>
							</div>
							<div v-if="selectedSalesPersons.length > 0" class="space-y-1">
								<div
									v-for="person in selectedSalesPersons"
									:key="person.sales_person"
									class="flex items-center justify-between p-2 bg-white border border-purple-200 rounded-lg text-xs"
								>
									<div class="flex items-center gap-2">
										<button @click="removeSalesPerson(person.sales_person)" class="text-purple-500 hover:text-purple-700">
											<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
												<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
											</svg>
										</button>
										<span class="font-medium">{{ person.sales_person_name || person.sales_person }}</span>
									</div>
									<input
										v-if="settingsStore.isMultipleSalesPersons"
										type="number"
										:value="person.allocated_percentage"
										@input="updateSalesPersonAllocation(person.sales_person, $event.target.value)"
										class="w-12 px-1 py-0.5 text-end border border-purple-300 rounded text-xs"
										min="0" max="100"
									/>
								</div>
							</div>
							<div v-if="filteredSalesPersons.length > 0 && salesPersonSearch" class="max-h-32 overflow-y-auto border border-purple-200 rounded-lg bg-white">
								<button
									v-for="person in filteredSalesPersons"
									:key="person.name"
									type="button"
									@click="addSalesPerson(person)"
									class="w-full text-start px-3 py-2 text-xs hover:bg-purple-50 border-b border-purple-100 last:border-0"
								>
									{{ person.sales_person_name || person.name }}
								</button>
							</div>
						</div>
					</details>

					<!-- Collapsible: Additional Discount -->
					<details v-if="settingsStore.allowAdditionalDiscount" class="group">
						<summary class="text-xs font-semibold text-orange-700 cursor-pointer hover:text-orange-900 list-none flex items-center gap-1">
							<svg class="w-3 h-3 transition-transform group-open:rotate-90" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
							</svg>
							{{ __('Additional Discount') }}
							<span v-if="localAdditionalDiscount > 0" class="text-red-500">
								(-{{ formatCurrency(additionalDiscountType === 'percentage' ? (subtotal * localAdditionalDiscount / 100) : localAdditionalDiscount) }})
							</span>
						</summary>
						<div class="mt-2 bg-orange-50 border border-orange-200 rounded-lg p-3">
							<div class="grid grid-cols-[90px_1fr] gap-2">
								<select
									v-model="additionalDiscountType"
									@change="handleAdditionalDiscountTypeChange"
									class="px-2 py-1.5 text-xs border border-orange-300 rounded-lg bg-white"
								>
									<option value="percentage">{{ __('% Percent') }}</option>
									<option value="amount">{{ __('{0} Amount', [currencySymbol]) }}</option>
								</select>
								<input
									type="number"
									v-model.number="localAdditionalDiscount"
									@input="handleAdditionalDiscountChange"
									placeholder="0.00"
									min="0"
									class="px-2 py-1.5 text-xs border border-orange-300 rounded-lg bg-white"
								/>
							</div>
						</div>
					</details>

					<!-- Primary Action Buttons -->
					<div class="flex gap-3 mt-auto pt-2">
						<button
							v-if="allowCreditSale"
							type="button"
							@click="addCreditAccountPayment"
							:disabled="paymentEntries.length > 0"
							:class="[
								'flex-1 inline-flex items-center justify-center gap-2 h-12 rounded-xl text-sm font-bold transition-colors touch-manipulation',
								paymentEntries.length > 0
									? 'bg-orange-200 text-white cursor-not-allowed'
									: 'bg-[#F37021] text-white hover:bg-[#e0651a] active:bg-[#d05a15]'
							]"
						>
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
							</svg>
							{{ __('Pay on Account') }}
						</button>
						<button
							type="button"
							@click="completePayment"
							:disabled="!canComplete"
							:class="[
								'flex-1 inline-flex items-center justify-center gap-2 h-12 rounded-xl text-sm font-bold transition-all touch-manipulation disabled:opacity-100',
								canComplete
									? 'bg-blue-700 text-white shadow-md hover:bg-blue-800 active:bg-blue-900 ring-2 ring-blue-700/25'
									: paymentEntries.length > 0
										? 'bg-blue-100 text-blue-700 cursor-not-allowed border border-blue-200'
										: 'bg-gray-200 text-gray-400 cursor-not-allowed'
							]"
						>
							<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
							</svg>
							{{ paymentButtonText }}
						</button>
					</div>
				</div>
			</div>
		</template>

		<template #actions>
			<div class="flex items-center justify-between w-full gap-2">
				<button
					v-if="paymentEntries.length > 0"
					@click="clearAll"
					class="inline-flex items-center gap-1.5 h-9 px-3 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
					</svg>
					{{ __('Clear All') }}
				</button>
				<div v-else></div>
				<button
					@click="show = false"
					class="inline-flex items-center h-9 px-4 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
				>
					{{ __('Cancel') }}
				</button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import PaymentKeypad from "@/components/sale/PaymentKeypad.vue"
import { usePOSSettingsStore } from "@/stores/posSettings"
import { formatCurrency as formatCurrencyUtil, getCurrencySymbol } from "@/utils/currency"
import { getPaymentIcon } from "@/utils/payment"
import { offlineWorker } from "@/utils/offline/workerClient"
import { Dialog, createResource } from "frappe-ui"
import { computed, nextTick, ref, watch } from "vue"
import { useToast } from "@/composables/useToast"

const settingsStore = usePOSSettingsStore()
const { showWarning } = useToast()

const props = defineProps({
	modelValue: Boolean,
	grandTotal: {
		type: Number,
		default: 0,
	},
	subtotal: {
		type: Number,
		default: 0,
	},
	taxAmount: {
		type: Number,
		default: 0,
	},
	discountAmount: {
		type: Number,
		default: 0,
	},
	items: {
		type: Array,
		default: () => [],
	},
	customerName: {
		type: String,
		default: "",
	},
	posProfile: String,
	currency: {
		type: String,
		default: "USD",
	},
	isOffline: {
		type: Boolean,
		default: false,
	},
	allowPartialPayment: {
		type: Boolean,
		default: false,
	},
	allowCreditSale: {
		type: Boolean,
		default: false,
	},
	customer: {
		type: [String, Object],
		default: null,
	},
	company: {
		type: String,
		default: "",
	},
	additionalDiscount: {
		type: Number,
		default: 0,
	},
})

const emit = defineEmits([
	"update:modelValue",
	"payment-completed",
	"update-additional-discount",
	"show-offers",
	"show-coupons",
])

const show = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
})

const paymentMethods = ref([])
const loadingPaymentMethods = ref(false)
const lastSelectedMethod = ref(null)
const keypadInput = ref("")
const keypadInputRef = ref(null)
const paymentEntries = ref([])
const customerCredit = ref([])
const customerBalance = ref({ total_outstanding: 0, total_credit: 0, net_balance: 0 })
const loadingCredit = ref(false)

const localAdditionalDiscount = ref(0)
const additionalDiscountType = ref(
	settingsStore.usePercentageDiscount ? 'percentage' : 'amount'
)

const customerDisplayName = computed(() => {
	if (props.customerName) return props.customerName
	const cust = props.customer
	if (cust && typeof cust === 'object') {
		return cust.customer_name || cust.name || __('Walk In')
	}
	return cust || __('Walk In')
})

const itemCountLabel = computed(() => {
	const count = props.items.length
	return count === 1 ? __('1 item') : __('{0} items', [count])
})

const keypadAmount = computed(() => {
	const val = Number.parseFloat(keypadInput.value)
	return Number.isNaN(val) ? 0 : val
})

const paymentMethodsResource = createResource({
	url: "pos_next.api.pos_profile.get_payment_methods",
	makeParams() {
		return {
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		paymentMethods.value = data?.message || data || []
		if (paymentMethods.value.length > 0) {
			const defaultMethod = paymentMethods.value.find((m) => m.default)
			lastSelectedMethod.value = defaultMethod || paymentMethods.value[0]
		}
	},
})

const customerCreditResource = createResource({
	url: "pos_next.api.credit_sales.get_available_credit",
	makeParams() {
		const customerName = props.customer?.name || props.customer
		return {
			customer: customerName,
			company: props.company,
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		customerCredit.value = data || []
		loadingCredit.value = false
	},
	onError() {
		customerCredit.value = []
		loadingCredit.value = false
	},
})

const customerBalanceResource = createResource({
	url: "pos_next.api.credit_sales.get_customer_balance",
	makeParams() {
		const customerName = props.customer?.name || props.customer
		return {
			customer: customerName,
			company: props.company,
		}
	},
	auto: false,
	onSuccess(data) {
		customerBalance.value = data || { total_outstanding: 0, total_credit: 0, net_balance: 0 }
	},
	onError() {
		customerBalance.value = { total_outstanding: 0, total_credit: 0, net_balance: 0 }
	},
})

const salesPersons = ref([])
const selectedSalesPersons = ref([])
const salesPersonSearch = ref('')
const loadingSalesPersons = ref(false)

const salesPersonsResource = createResource({
	url: "pos_next.api.pos_profile.get_sales_persons",
	makeParams() {
		return {
			pos_profile: props.posProfile,
		}
	},
	auto: false,
	onSuccess(data) {
		salesPersons.value = data?.message || data || []
		loadingSalesPersons.value = false
	},
	onError() {
		salesPersons.value = []
		loadingSalesPersons.value = false
	},
})

const filteredSalesPersons = computed(() => {
	if (!salesPersonSearch.value) return []

	const searchLower = salesPersonSearch.value.toLowerCase()
	const selectedIds = selectedSalesPersons.value.map(p => p.sales_person)

	return salesPersons.value
		.filter(person => {
			if (selectedIds.includes(person.name)) return false
			const name = (person.sales_person_name || person.name || '').toLowerCase()
			return name.includes(searchLower)
		})
		.slice(0, 10)
})

function addSalesPerson(person) {
	if (settingsStore.isSingleSalesPerson) {
		selectedSalesPersons.value = [{
			sales_person: person.name,
			sales_person_name: person.sales_person_name || person.name,
			allocated_percentage: 100,
			commission_rate: person.commission_rate,
		}]
	} else {
		const defaultAllocation = selectedSalesPersons.value.length === 0 ? 100 : 0
		selectedSalesPersons.value.push({
			sales_person: person.name,
			sales_person_name: person.sales_person_name || person.name,
			allocated_percentage: defaultAllocation,
			commission_rate: person.commission_rate,
		})
	}
	salesPersonSearch.value = ''
}

function removeSalesPerson(personName) {
	const index = selectedSalesPersons.value.findIndex(p => p.sales_person === personName)
	if (index > -1) selectedSalesPersons.value.splice(index, 1)
}

function updateSalesPersonAllocation(personName, value) {
	const person = selectedSalesPersons.value.find(p => p.sales_person === personName)
	if (person) person.allocated_percentage = Number.parseFloat(value) || 0
}

async function loadPaymentMethods() {
	if (!props.posProfile || loadingPaymentMethods.value) return

	loadingPaymentMethods.value = true
	try {
		if (props.isOffline) {
			const cached = await offlineWorker.getCachedPaymentMethods(props.posProfile)
			if (cached && cached.length > 0) {
				paymentMethods.value = cached
				if (paymentMethods.value.length > 0) {
					const defaultMethod = paymentMethods.value.find((m) => m.default)
					lastSelectedMethod.value = defaultMethod || paymentMethods.value[0]
				}
			}
		} else {
			await paymentMethodsResource.fetch()
		}
	} catch (error) {
		console.error("Error loading payment methods:", error)
	} finally {
		loadingPaymentMethods.value = false
	}
}

const currencySymbol = computed(() => getCurrencySymbol(props.currency))
const round2 = (val) => Number(Number(val).toFixed(2))

const totalPaid = computed(() => {
	const sum = paymentEntries.value.reduce((sum, entry) => sum + (entry.amount || 0), 0)
	return round2(sum)
})

const totalAvailableCredit = computed(() => round2(-customerBalance.value.net_balance))

const remainingAmount = computed(() => {
	const remaining = round2(props.grandTotal) - totalPaid.value
	return remaining > 0 ? round2(remaining) : 0
})

const changeAmount = computed(() => {
	const change = totalPaid.value - round2(props.grandTotal)
	return change > 0 ? round2(change) : 0
})

const canComplete = computed(() => {
	if (props.allowPartialPayment) {
		return totalPaid.value > 0 && paymentEntries.value.length > 0
	}
	return remainingAmount.value === 0 && paymentEntries.value.length > 0
})

const paymentButtonText = computed(() => {
	if (remainingAmount.value === 0) return __("Complete Payment")
	if (props.allowPartialPayment && totalPaid.value > 0) return __("Partial Payment")
	return __("Complete Payment")
})

const quickAmounts = computed(() => {
	const remaining = remainingAmount.value
	if (remaining <= 0) return [10, 20, 50, 100]

	const amounts = new Set()
	const exactAmount = Math.ceil(remaining)
	amounts.add(exactAmount)

	let denominations
	if (remaining < 20) denominations = [5, 10, 20, 50]
	else if (remaining < 100) denominations = [10, 20, 50, 100]
	else if (remaining < 500) denominations = [50, 100, 200, 500]
	else if (remaining < 2000) denominations = [100, 200, 500, 1000]
	else denominations = [500, 1000, 2000, 5000]

	const minGap = Math.max(5, exactAmount * 0.05)
	const isFarEnough = (newAmt) => {
		for (const existing of amounts) {
			if (Math.abs(newAmt - existing) < minGap) return false
		}
		return true
	}

	for (const denom of denominations) {
		if (amounts.size >= 4) break
		const roundedUp = Math.ceil(remaining / denom) * denom
		if (roundedUp > exactAmount && isFarEnough(roundedUp)) amounts.add(roundedUp)
		if (amounts.size < 4) {
			const oneStepUp = roundedUp + denom
			if (oneStepUp > exactAmount && isFarEnough(oneStepUp)) amounts.add(oneStepUp)
		}
	}

	return Array.from(amounts).filter((amt) => amt > 0).sort((a, b) => a - b).slice(0, 4)
})

watch(
	() => props.posProfile,
	(newProfile) => {
		if (newProfile) {
			loadPaymentMethods()
			if (settingsStore.enableSalesPersons && salesPersons.value.length === 0) {
				loadingSalesPersons.value = true
				salesPersonsResource.fetch()
			}
		}
	},
	{ immediate: true }
)

watch(show, (newVal) => {
	if (newVal) {
		paymentEntries.value = []
		keypadInput.value = ""
		lastSelectedMethod.value = null
		customerCredit.value = []
		customerBalance.value = { total_outstanding: 0, total_credit: 0, net_balance: 0 }
		selectedSalesPersons.value = []
		salesPersonSearch.value = ''

		if (paymentMethods.value.length > 0 && !lastSelectedMethod.value) {
			const defaultMethod = paymentMethods.value.find((m) => m.default)
			lastSelectedMethod.value = defaultMethod || paymentMethods.value[0]
		}

		if (props.allowCreditSale && props.customer && props.company) {
			loadingCredit.value = true
			customerCreditResource.fetch()
			customerBalanceResource.fetch()
		}

		focusKeypadInput()
	}
})

function selectPaymentMethod(method) {
	lastSelectedMethod.value = method
	keypadInput.value = ""
	focusKeypadInput()
}

function sanitizeKeypadValue(value) {
	let sanitized = value.replace(/[^\d.]/g, "")
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

function handleKeypadInputChange(event) {
	keypadInput.value = sanitizeKeypadValue(event.target.value)
}

function handlePaymentKeydown(event) {
	const target = event.target

	// Let the amount input handle typing natively when focused
	if (target === keypadInputRef.value) return

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
		handleKeypadAdd()
		return
	}
	if (event.key === "Backspace") {
		event.preventDefault()
		handleBackspace()
		return
	}
	if (event.key === "Escape") {
		event.preventDefault()
		handleClearKeypad()
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

function handleKeyPress(key) {
	if (key === ".") {
		if (keypadInput.value.includes(".")) return
		keypadInput.value = keypadInput.value ? `${keypadInput.value}.` : "0."
		return
	}
	if (key === "00") {
		if (!keypadInput.value || keypadInput.value === "0") {
			keypadInput.value = "0"
			return
		}
		keypadInput.value += "00"
		return
	}
	if (keypadInput.value === "0" && key !== ".") {
		keypadInput.value = key
	} else {
		keypadInput.value += key
	}
}

function focusKeypadInput() {
	nextTick(() => keypadInputRef.value?.focus())
}

function handleBackspace() {
	keypadInput.value = keypadInput.value.slice(0, -1)
}

function handleClearKeypad() {
	keypadInput.value = ""
}

function handleKeypadAdd() {
	if (!lastSelectedMethod.value || !keypadAmount.value || keypadAmount.value <= 0) return
	addCustomPayment(lastSelectedMethod.value, keypadAmount.value)
	keypadInput.value = ""
}

function addCustomPayment(method, amount) {
	const amt = Number.parseFloat(amount)
	if (!amt || amt <= 0) return

	paymentEntries.value.push({
		mode_of_payment: method.mode_of_payment,
		amount: amt,
		type: method.type || __('Cash'),
	})
	keypadInput.value = ""
}

function applyCustomerCredit() {
	if (remainingAmount.value === 0 || totalAvailableCredit.value === 0) return

	const creditToApply = Math.min(remainingAmount.value, totalAvailableCredit.value)
	paymentEntries.value.push({
		mode_of_payment: "Customer Credit",
		amount: Number.parseFloat(creditToApply.toFixed(2)),
		type: "Credit",
		is_customer_credit: true,
		credit_details: customerCredit.value.map(credit => ({
			...credit,
			credit_to_redeem: 0,
		})),
	})
}

function addCreditAccountPayment() {
	const paymentData = {
		payments: [],
		change_amount: 0,
		is_partial_payment: false,
		is_credit_sale: true,
		paid_amount: 0,
		outstanding_amount: props.grandTotal,
	}
	emit("payment-completed", paymentData)
	show.value = false
}

function removePaymentEntry(index) {
	paymentEntries.value.splice(index, 1)
}

function clearAll() {
	paymentEntries.value = []
	keypadInput.value = ""
}

function completePayment() {
	if (!canComplete.value) return

	const isPartial = totalPaid.value < props.grandTotal
	emit("payment-completed", {
		payments: paymentEntries.value,
		change_amount: changeAmount.value,
		is_partial_payment: isPartial,
		paid_amount: totalPaid.value,
		outstanding_amount: isPartial ? remainingAmount.value : 0,
		sales_team: selectedSalesPersons.value.length > 0 ? selectedSalesPersons.value : null,
	})
	show.value = false
}

function formatCurrency(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency)
}

function getMethodTotal(methodName) {
	return paymentEntries.value
		.filter((entry) => entry.mode_of_payment === methodName)
		.reduce((sum, entry) => sum + (entry.amount || 0), 0)
}

function getItemTotal(item) {
	if (item.amount) return item.amount
	const rate = item.rate || item.price_list_rate || 0
	return (item.quantity || 0) * rate
}

function handleAdditionalDiscountChange() {
	let discountValue = localAdditionalDiscount.value
	let discountAmount = 0

	if (additionalDiscountType.value === 'percentage') {
		if (settingsStore.maxDiscountAllowed > 0 && discountValue > settingsStore.maxDiscountAllowed) {
			localAdditionalDiscount.value = settingsStore.maxDiscountAllowed
			discountValue = settingsStore.maxDiscountAllowed
			showWarning(__('Maximum allowed discount is {0}%', [settingsStore.maxDiscountAllowed]))
		}
		if (discountValue > 100) {
			localAdditionalDiscount.value = 100
			discountValue = 100
		}
		discountAmount = (props.subtotal * discountValue) / 100
	} else {
		discountAmount = discountValue
		if (settingsStore.maxDiscountAllowed > 0 && props.subtotal > 0) {
			const percentageEquivalent = (discountAmount / props.subtotal) * 100
			if (percentageEquivalent > settingsStore.maxDiscountAllowed) {
				const maxAmount = (props.subtotal * settingsStore.maxDiscountAllowed) / 100
				localAdditionalDiscount.value = maxAmount
				discountAmount = maxAmount
				showWarning(__('Maximum allowed discount is {0}% ({1} {2})',
					[settingsStore.maxDiscountAllowed, props.currency, maxAmount.toFixed(2)]))
			}
		}
	}

	if (discountAmount > props.subtotal) {
		if (additionalDiscountType.value === 'amount') localAdditionalDiscount.value = props.subtotal
		discountAmount = props.subtotal
	}
	if (discountAmount < 0) {
		localAdditionalDiscount.value = 0
		discountAmount = 0
	}

	emit("update-additional-discount", discountAmount)
}

function handleAdditionalDiscountTypeChange() {
	handleAdditionalDiscountChange()
}

watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) localAdditionalDiscount.value = props.additionalDiscount || 0
	},
)
</script>
