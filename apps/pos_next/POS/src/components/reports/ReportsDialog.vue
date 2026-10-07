<template>
	<Transition name="fade">
	<div
		v-if="show"
		class="fixed inset-0 z-[300]"
	>
		<div
			class="fixed inset-0 bg-black bg-opacity-50"
			@click="handleBackdropClick"
		></div>
		<div class="fixed inset-0 flex items-center justify-center p-4 pointer-events-none">
			<div
				class="w-full h-full max-w-[95vw] max-h-[95vh] bg-white rounded-lg shadow-2xl overflow-hidden flex flex-col pointer-events-auto"
				@click.stop
			>
					<!-- Header -->
					<div class="flex items-center justify-between px-6 py-5 border-b bg-gradient-to-r from-indigo-50 to-purple-50">
						<div class="flex items-center gap-3">
							<div class="p-2 bg-indigo-100 rounded-lg">
								<svg class="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
								</svg>
							</div>
							<div>
								<h2 class="text-xl font-bold text-gray-900">{{ __('Reports') }}</h2>
								<p class="text-sm text-gray-600 flex items-center mt-0.5">
									{{ posProfile || __('POS Overview') }}
									<span v-if="activePeriodLabel" class="text-gray-400"> · {{ activePeriodLabel }}</span>
								</p>
							</div>
						</div>
						<div class="flex items-center gap-2">
							<Button
								@click="handleOpenInvoices"
								variant="ghost"
								size="sm"
							>
								<template #prefix>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
									</svg>
								</template>
								{{ labels.viewInvoices }}
							</Button>
							<Button
								@click="loadAllData"
								:loading="loading"
								variant="ghost"
								size="sm"
							>
								<template #prefix>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
									</svg>
								</template>
								{{ __('Refresh') }}
							</Button>
							<button
								@click="handleClose"
								class="p-2 hover:bg-white/50 rounded-lg transition-colors"
							>
								<svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
								</svg>
							</button>
						</div>
					</div>

					<!-- Period tabs (same pattern as Invoice Management) -->
					<div class="border-b border-gray-200 bg-gray-50">
						<nav class="flex gap-2 px-6 overflow-x-auto" :aria-label="__('Tabs')">
							<button
								v-for="option in periodTabs"
								:key="option.id"
								@click="setPeriod(option.id)"
								:class="[
									'px-4 py-3 text-sm font-semibold transition-all border-b-2 relative whitespace-nowrap',
									selectedPeriod === option.id
										? option.activeClass
										: 'text-gray-600 border-transparent hover:text-gray-800 hover:border-gray-300',
								]"
							>
								<div class="flex items-center gap-2">
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="option.icon"/>
									</svg>
									<span>{{ option.label }}</span>
								</div>
							</button>
						</nav>
					</div>

					<!-- Content -->
					<div class="flex-1 overflow-y-auto bg-gray-50">
						<div v-if="loading && !reportData" class="flex flex-col items-center justify-center py-16">
							<div class="animate-spin rounded-full h-12 w-12 border-b-3 border-indigo-500 mb-4"></div>
							<p class="text-sm font-medium text-gray-600">{{ __('Loading reports...') }}</p>
						</div>

						<div v-else class="p-6 flex flex-col gap-6">
							<!-- Custom date filters -->
							<div v-if="selectedPeriod === 'custom'" class="flex flex-wrap items-end gap-3">
								<div>
									<label class="block text-xs font-medium text-gray-600 mb-1">{{ __('From Date') }}</label>
									<input
										v-model="customFromDate"
										type="date"
										class="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
									/>
								</div>
								<div>
									<label class="block text-xs font-medium text-gray-600 mb-1">{{ __('To Date') }}</label>
									<input
										v-model="customToDate"
										type="date"
										class="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
									/>
								</div>
								<button
									@click="loadSalesReport"
									class="px-4 py-2 rounded-lg font-medium text-sm transition-all bg-indigo-600 text-white shadow-md hover:bg-indigo-700"
								>
									{{ __('Apply') }}
								</button>
							</div>

							<p v-if="periodRangeLabel" class="text-xs text-gray-500 -mt-2">
								{{ periodRangeLabel }}
							</p>

							<div
								v-if="selectedPeriod === 'session' && !hasOpenShift"
								class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-4"
							>
								{{ __('No open shift. Open a shift to view session report, or choose another period.') }}
							</div>

							<!-- Main summary banner -->
							<div class="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-200 rounded-lg p-4">
								<div class="flex flex-wrap items-center justify-between gap-4">
									<div>
										<div class="text-sm text-indigo-600 font-medium">{{ __('Net Total') }}</div>
										<div class="text-2xl font-bold text-gray-900 mt-1">{{ formatMoney(summary.net_total) }}</div>
										<div class="text-xs text-gray-600 mt-1">{{ labels.afterReturns }}</div>
									</div>
									<div class="flex flex-wrap gap-6 text-end">
										<div>
											<div class="text-xs text-gray-600">{{ __('Sales') }}</div>
											<div class="text-sm font-semibold text-gray-900 mt-1">{{ formatMoney(summary.sales_total) }}</div>
											<div class="text-xs text-gray-500">{{ labels.invoices(summary.sales_count) }}</div>
										</div>
										<div>
											<div class="text-xs text-gray-600">{{ returnsTotalLabel }}</div>
											<div class="text-sm font-semibold text-red-600 mt-1">{{ formatMoney(summary.returns_total) }}</div>
											<div class="text-xs text-gray-500">{{ labels.returns(summary.returns_count) }}</div>
										</div>
										<div>
											<div class="text-xs text-gray-600">{{ __('Outstanding') }}</div>
											<div class="text-sm font-semibold text-orange-600 mt-1">{{ formatMoney(unpaidSummary.total_outstanding) }}</div>
											<div class="text-xs text-gray-500">{{ labels.unpaid(unpaidSummary.count) }}</div>
										</div>
									</div>
								</div>
							</div>

							<!-- Stat cards -->
							<div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
								<div class="text-center p-4 bg-white rounded-xl shadow-sm border border-gray-200">
									<div class="text-xs text-gray-600 mb-1">{{ __('Sales') }}</div>
									<div class="text-lg font-bold text-gray-900">{{ formatMoney(summary.sales_total) }}</div>
									<div class="text-xs text-gray-500 mt-1">{{ labels.invoices(summary.sales_count) }}</div>
								</div>
								<div class="text-center p-4 bg-white rounded-xl shadow-sm border border-gray-200">
									<div class="text-xs text-gray-600 mb-1">{{ returnsTotalLabel }}</div>
									<div class="text-lg font-bold text-red-600">{{ formatMoney(summary.returns_total) }}</div>
									<div class="text-xs text-gray-500 mt-1">{{ labels.returns(summary.returns_count) }}</div>
								</div>
								<div class="text-center p-4 bg-white rounded-xl shadow-sm border border-gray-200">
									<div class="text-xs text-gray-600 mb-1">{{ __('Items Sold') }}</div>
									<div class="text-lg font-bold text-gray-900">{{ formatQuantity(summary.items_sold) }}</div>
									<div v-if="summary.items_returned > 0" class="text-xs text-red-500 mt-1">
										{{ labels.returned(formatQuantity(summary.items_returned)) }}
									</div>
								</div>
								<div class="text-center p-4 bg-white rounded-xl shadow-sm border border-gray-200">
									<div class="text-xs text-gray-600 mb-1">{{ __('Partially Paid') }}</div>
									<div class="text-lg font-bold text-orange-600">{{ formatMoney(partialSummary.total_outstanding) }}</div>
									<div class="text-xs text-gray-500 mt-1">{{ partialSummary.count }} {{ __('Count') }}</div>
								</div>
							</div>

							<div class="grid lg:grid-cols-2 gap-4">
								<!-- Payment breakdown -->
								<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
									<div class="px-5 py-4 border-b bg-gradient-to-r from-indigo-50 to-blue-50">
										<h3 class="text-base font-bold text-gray-900">{{ __('Payment Breakdown') }}</h3>
									</div>
									<div v-if="paymentBreakdown.length" class="p-4">
										<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
											<div
												v-for="(row, idx) in paymentBreakdown"
												:key="idx"
												class="flex items-center justify-between p-3 rounded-lg border bg-gray-50 border-gray-200 text-sm"
											>
												<span class="text-gray-700 font-medium">{{ row.mode_of_payment }}</span>
												<span class="font-semibold text-gray-900">{{ formatMoney(row.amount) }}</span>
											</div>
										</div>
									</div>
									<div v-else class="flex flex-col items-center justify-center py-12 text-center px-4">
										<svg class="w-12 h-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
										</svg>
										<p class="text-gray-600 font-medium text-sm">{{ __('No payments in this period.') }}</p>
									</div>
								</div>

								<!-- Returns -->
								<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
									<div class="px-5 py-4 border-b bg-gradient-to-r from-red-50 to-orange-50 flex items-center justify-between">
										<h3 class="text-base font-bold text-gray-900">
											{{ selectedPeriod === 'session' ? labels.returnsThisShift : labels.returnsInPeriod }}
										</h3>
										<span class="px-2 py-0.5 text-xs font-bold rounded-full bg-red-100 text-red-700">
											{{ summary.returns_count }}
										</span>
									</div>
									<div v-if="reportLoading" class="flex flex-col items-center justify-center py-12">
										<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500 mb-3"></div>
										<p class="text-sm text-gray-500">{{ __('Loading returns...') }}</p>
									</div>
									<div v-else-if="returnsList.length" class="flex flex-col gap-3 p-4 max-h-[28rem] overflow-y-auto">
										<div
											v-for="item in returnsList"
											:key="item.name"
											class="bg-white border border-red-200 rounded-lg p-4 hover:shadow-md transition-all cursor-pointer"
											@click="handleViewReturn(item)"
										>
											<div class="flex items-start justify-between gap-3">
												<div class="flex-1 min-w-0">
													<div class="flex items-center gap-2 mb-1">
														<h4 dir="ltr" class="text-sm font-semibold text-gray-900">{{ item.name }}</h4>
														<span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-700 shrink-0">
															{{ __('Return') }}
														</span>
													</div>
													<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600">
														<span>{{ item.customer_name || item.customer }}</span>
														<span>{{ formatDate(item.posting_date) }}</span>
														<span v-if="item.return_against" dir="ltr">{{ labels.against(item.return_against) }}</span>
													</div>
												</div>
												<div dir="ltr" class="text-sm font-bold text-red-600 text-end shrink-0">
													-{{ formatMoney(Math.abs(item.grand_total || 0)) }}
												</div>
											</div>
										</div>
										<p
											v-if="returnsList.length < summary.returns_count"
											class="text-xs text-center text-amber-700 pt-1"
										>
											{{ labels.showingReturns(returnsList.length, summary.returns_count) }}
										</p>
									</div>
									<div v-else class="flex flex-col items-center justify-center py-12 text-center px-4">
										<svg class="w-12 h-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
										</svg>
										<p class="text-gray-600 font-medium text-sm">
											{{ selectedPeriod === 'session' ? labels.noReturnsShift : labels.noReturnsPeriod }}
										</p>
									</div>
								</div>
							</div>

							<!-- Recent transactions -->
							<div>
								<h3 class="text-base font-bold text-gray-900 mb-4">{{ labels.recentTransactions }}</h3>
								<div v-if="recentInvoices.length" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
									<div
										v-for="item in recentInvoices"
										:key="item.name"
										class="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-lg transition-all overflow-hidden"
									>
										<div
											:class="[
												'px-5 py-4 border-b border-gray-200',
												item.is_return
													? 'bg-gradient-to-r from-red-50 to-orange-50'
													: 'bg-gradient-to-r from-indigo-50 to-blue-50',
											]"
										>
											<div class="flex items-start justify-between gap-2">
												<div class="min-w-0">
													<h4 class="text-base font-bold text-gray-900 truncate">{{ item.name }}</h4>
													<div class="flex items-center gap-2 mt-1">
														<span
															v-if="item.is_return"
															class="text-xs px-2.5 py-1 rounded-full font-semibold bg-red-100 text-red-700"
														>
															{{ __('Return') }}
														</span>
														<span v-else class="text-xs px-2.5 py-1 rounded-full font-semibold bg-green-100 text-green-700">
															{{ __('Paid') }}
														</span>
													</div>
												</div>
												<div :class="['text-base font-bold shrink-0', item.is_return ? 'text-red-600' : 'text-gray-900']">
													{{ formatMoney(item.grand_total) }}
												</div>
											</div>
										</div>
										<div class="px-5 py-3 text-sm text-gray-600">
											<div class="flex items-center gap-1">
												<svg class="w-4 h-4 me-1 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
												</svg>
												<span class="truncate">{{ item.customer_name || item.customer }}</span>
											</div>
										</div>
									</div>
								</div>
								<div v-else class="flex flex-col items-center justify-center py-16 text-center">
									<svg class="w-16 h-16 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
									</svg>
									<p class="text-gray-600 font-medium">{{ __('No transactions in this period.') }}</p>
								</div>
							</div>

							<!-- Activity & sync -->
							<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
								<div class="px-5 py-4 border-b bg-gradient-to-r from-indigo-50 to-purple-50">
									<h3 class="text-base font-bold text-gray-900">{{ __('Activity & Sync') }}</h3>
								</div>
								<div class="p-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
									<div class="text-center p-3 bg-purple-50 rounded-lg border border-purple-100">
										<div class="text-xs text-gray-600 mb-1">{{ __('Draft Invoices') }}</div>
										<div class="text-lg font-bold text-purple-700">{{ draftsCount }}</div>
									</div>
									<div class="text-center p-3 bg-orange-50 rounded-lg border border-orange-100">
										<div class="text-xs text-gray-600 mb-1">{{ __('Pending Sync') }}</div>
										<div class="text-lg font-bold text-orange-700">{{ pendingOfflineCount }}</div>
									</div>
									<div class="text-center p-3 rounded-lg border border-gray-200 bg-gray-50">
										<div class="text-xs text-gray-600 mb-1">{{ __('Connection') }}</div>
										<div :class="['text-lg font-bold', isOffline ? 'text-red-600' : 'text-green-600']">
											{{ isOffline ? __('Offline') : __('Online') }}
										</div>
									</div>
									<div class="text-center p-3 bg-green-50 rounded-lg border border-green-100">
										<div class="text-xs text-gray-600 mb-1">{{ __('Shift Status') }}</div>
										<div :class="['text-lg font-bold', hasOpenShift ? 'text-green-600' : 'text-gray-500']">
											{{ hasOpenShift ? __('Open') : __('Closed') }}
										</div>
										<div v-if="hasOpenShift && shiftDuration" class="text-xs text-gray-500 mt-1">{{ shiftDuration }}</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup>
import { useFormatters } from "@/composables/useFormatters"
import { formatCurrency as formatCurrencyUtil } from "@/utils/currency"
import { translationVersion } from "@/utils/translation"
import { Button, call } from "frappe-ui"
import { computed, ref, watch } from "vue"

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	posProfile: { type: String, default: "" },
	currency: { type: String, default: "USD" },
	openingShift: { type: String, default: "" },
	hasOpenShift: { type: Boolean, default: false },
	shiftDuration: { type: String, default: "" },
	draftsCount: { type: Number, default: 0 },
	pendingOfflineCount: { type: Number, default: 0 },
	isOffline: { type: Boolean, default: false },
})

const emit = defineEmits(["update:modelValue", "open-invoices", "refresh-history", "view-invoice"])

const show = ref(props.modelValue)
const loading = ref(false)
const reportLoading = ref(false)
const selectedPeriod = ref("session")
const customFromDate = ref("")
const customToDate = ref("")
const reportData = ref(null)
const unpaidSummary = ref({ count: 0, total_outstanding: 0, total_paid: 0 })
const partialSummary = ref({ count: 0, total_outstanding: 0, total_paid: 0 })
const openedAt = ref(0)

const { formatDate, formatDateTime, formatQuantity } = useFormatters()

const periodTabs = computed(() => {
	translationVersion.value
	return [
		{
			id: "session",
			label: __("This Shift"),
			icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
			activeClass: "text-indigo-600 border-indigo-500",
		},
		{
			id: "yesterday",
			label: __("Yesterday"),
			icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
			activeClass: "text-orange-600 border-orange-500",
		},
		{
			id: "week",
			label: __("This Week"),
			icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2",
			activeClass: "text-indigo-600 border-indigo-500",
		},
		{
			id: "month",
			label: __("This Month"),
			icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
			activeClass: "text-purple-600 border-purple-500",
		},
		{
			id: "custom",
			label: __("Custom"),
			icon: "M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z",
			activeClass: "text-gray-800 border-gray-500",
		},
	]
})

const labels = computed(() => {
	translationVersion.value
	return {
		returnsThisShift: __("Returns This Shift"),
		returnsInPeriod: __("Returns in Period"),
		recentTransactions: __("Recent Transactions"),
		viewInvoices: __("View Invoices"),
		afterReturns: __("After returns"),
		invoices: (count) => __("{0} invoices", [count]),
		returns: (count) => __("{0} returns", [count]),
		returned: (count) => __("{0} returned", [count]),
		unpaid: (count) => __("{0} unpaid", [count]),
		against: (name) => __("Against {0}", [name]),
		noReturnsShift: __("No returns made in this shift."),
		noReturnsPeriod: __("No returns in this period."),
		showingReturns: (shown, total) => __("Showing {0} of {1} returns", [shown, total]),
		shiftStarted: (when) => __("Shift started {0}", [when]),
		currentShift: __("Current shift"),
	}
})

const activePeriodLabel = computed(() => {
	translationVersion.value
	return periodTabs.value.find((option) => option.id === selectedPeriod.value)?.label || ""
})

const returnsTotalLabel = computed(() => {
	translationVersion.value
	return selectedPeriod.value === "session"
		? __("Total Returns (This Shift)")
		: __("Total Returns")
})

const summary = computed(() => reportData.value?.summary || {
	sales_count: 0,
	sales_total: 0,
	returns_count: 0,
	returns_total: 0,
	net_total: 0,
	items_sold: 0,
	items_returned: 0,
})

const paymentBreakdown = computed(() => reportData.value?.payment_breakdown || [])
const returnsList = computed(() => {
	const returns = reportData.value?.returns
	if (!Array.isArray(returns)) return []
	return returns.filter((item) => item?.name)
})
const recentInvoices = computed(() => reportData.value?.recent_invoices || [])

const periodRangeLabel = computed(() => {
	if (!reportData.value) return ""
	if (selectedPeriod.value === "session") {
		if (!props.hasOpenShift) return ""
		if (reportData.value.from_date) {
			return labels.value.shiftStarted(formatDateTime(reportData.value.from_date))
		}
		return labels.value.currentShift
	}
	if (reportData.value.from_date && reportData.value.to_date) {
		if (reportData.value.from_date === reportData.value.to_date) {
			return formatDate(reportData.value.from_date)
		}
		return `${formatDate(reportData.value.from_date)} – ${formatDate(reportData.value.to_date)}`
	}
	return ""
})

watch(
	() => props.modelValue,
	(val) => {
		show.value = val
		if (val) {
			openedAt.value = Date.now()
			initCustomDates()
			emit("refresh-history")
			loadAllData()
		}
	},
)

watch(show, (val) => emit("update:modelValue", val))

function initCustomDates() {
	const today = new Date()
	const weekAgo = new Date(today)
	weekAgo.setDate(today.getDate() - 7)
	customToDate.value = toDateInputValue(today)
	customFromDate.value = toDateInputValue(weekAgo)
}

function toDateInputValue(date) {
	return date.toISOString().slice(0, 10)
}

function formatMoney(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency)
}

function setPeriod(period) {
	selectedPeriod.value = period
	if (period !== "custom") {
		loadSalesReport()
	}
}

async function loadSalesReport() {
	if (!props.posProfile) return

	if (selectedPeriod.value === "custom") {
		if (!customFromDate.value || !customToDate.value) return
	}

	reportLoading.value = true
	try {
		const params = {
			pos_profile: props.posProfile,
			period: selectedPeriod.value,
		}

		if (selectedPeriod.value === "session" && props.openingShift) {
			params.pos_opening_shift = props.openingShift
		}

		if (selectedPeriod.value === "custom") {
			params.from_date = customFromDate.value
			params.to_date = customToDate.value
		}

		reportData.value = await call("pos_next.api.reports.get_sales_report", params)
	} catch (error) {
		console.error("[ReportsDialog] Error loading sales report:", error)
		reportData.value = {
			summary: {
				sales_count: 0,
				sales_total: 0,
				returns_count: 0,
				returns_total: 0,
				net_total: 0,
				items_sold: 0,
				items_returned: 0,
			},
			payment_breakdown: [],
			returns: [],
			recent_invoices: [],
		}
	} finally {
		reportLoading.value = false
	}
}

async function loadPaymentSummaries() {
	if (!props.posProfile) return

	try {
		const [unpaid, partial] = await Promise.all([
			call("pos_next.api.partial_payments.get_unpaid_summary", { pos_profile: props.posProfile }),
			call("pos_next.api.partial_payments.get_partial_payment_summary", { pos_profile: props.posProfile }),
		])
		unpaidSummary.value = unpaid || unpaidSummary.value
		partialSummary.value = partial || partialSummary.value
	} catch (error) {
		console.error("[ReportsDialog] Error loading payment summaries:", error)
	}
}

async function loadAllData() {
	loading.value = true
	try {
		await Promise.all([loadSalesReport(), loadPaymentSummaries()])
	} finally {
		loading.value = false
	}
}

function handleBackdropClick() {
	if (Date.now() - openedAt.value < 300) return
	handleClose()
}

function handleClose() {
	show.value = false
}

function handleOpenInvoices() {
	show.value = false
	emit("open-invoices")
}

function handleViewReturn(item) {
	emit("view-invoice", item)
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
</style>
