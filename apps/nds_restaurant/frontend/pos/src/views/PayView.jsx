import React, { useState } from "react";

export default function PayView({ total, payments, pay, setView, context }) {
  const enableDiscount = context?.settings?.enable_discount;
  const [discountType, setDiscountType] = useState("percent"); // 'percent' or 'amount'
  const [discountVal, setDiscountVal] = useState(0);


  let calculatedDiscount = 0;
  if (discountType === "percent") {
    calculatedDiscount = (total * (parseFloat(discountVal) || 0)) / 100;
  } else {
    calculatedDiscount = parseFloat(discountVal) || 0;
  }

  const finalTotal = Math.max(0, total - calculatedDiscount);

  const handlePay = (mop) => {
    const discPct = discountType === "percent" ? parseFloat(discountVal) || 0 : 0;
    const discAmt = discountType === "amount" ? parseFloat(discountVal) || 0 : 0;
    pay(mop, discPct, discAmt, finalTotal);
  };

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="bg-black/30 border border-white/10 rounded-xl p-6 w-full max-w-md">
        <h2 className="font-display text-2xl mb-2 text-white">Payment</h2>

        <div className="mb-4">
          <p className="text-gray-400 text-sm">Subtotal: {total.toFixed(2)} SAR</p>
          {enableDiscount && discountVal > 0 && (
            <p className="text-amber-400 text-sm">Discount: -{calculatedDiscount.toFixed(2)} SAR</p>
          )}
          <p className="text-emerald-400 text-xl font-bold mt-1">Total: {finalTotal.toFixed(2)} SAR</p>
        </div>

        {/* Discount Controls */}
        {enableDiscount && (
          <div className="bg-black/20 p-3 rounded-lg border border-white/5 mb-4">
            <label className="text-xs text-gray-400 mb-1 block">Apply Discount</label>
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => setDiscountType("percent")}
                className={`flex-1 py-1 rounded text-xs font-bold ${
                  discountType === "percent" ? "bg-amber-500 text-black" : "bg-white/10 text-gray-300"
                }`}
              >
                % Percentage
              </button>
              <button
                type="button"
                onClick={() => setDiscountType("amount")}
                className={`flex-1 py-1 rounded text-xs font-bold ${
                  discountType === "amount" ? "bg-amber-500 text-black" : "bg-white/10 text-gray-300"
                }`}
              >
                Amount (SAR)
              </button>
            </div>
            <input
              type="number"
              min="0"
              placeholder={discountType === "percent" ? "Discount %" : "Discount Amount"}
              value={discountVal || ""}
              onChange={(e) => setDiscountVal(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500"
            />
          </div>
        )}

        {/* Payment Buttons */}
        <div className="space-y-2">
          {(payments || []).map((p) => (
            <button
              key={p.mode_of_payment}
              onClick={() => handlePay(p.mode_of_payment)}
              className="w-full py-3 rounded bg-amber-500 text-black font-semibold hover:bg-amber-400 transition"
            >
              Pay {finalTotal.toFixed(2)} SAR with {p.mode_of_payment}
            </button>
          ))}
        </div>

        <button onClick={() => setView("menu")} className="mt-4 text-sm text-gray-400 hover:text-white underline block text-center w-full">
          Back
        </button>
      </div>
    </div>
  );
}