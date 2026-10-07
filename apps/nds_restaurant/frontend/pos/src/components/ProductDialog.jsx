/**
 * P3-T5: Product dialog for variants, add-ons, notes and quantity
 * Opens on double-click. Single click still adds directly to cart.
 */
import { useState, useEffect } from "react";
import { ItemImage } from "../views/MenuView";

export function variantLabel(parentName, v) {
  if (v && typeof v === "object" && v.label) return v.label;
  const name = String((v && typeof v === "object" ? v.item_name || v.item : v) || "").trim();
  const parent = String(parentName || "").trim();
  if (parent && name.toLowerCase().startsWith(parent.toLowerCase()) && name.length > parent.length) {
    const short = name.slice(parent.length).replace(/^[\s\-_/:()]+|[\s\-_/:()]+$/g, "");
    if (short) return short;
  }
  return name;
}

export default function ProductDialog({ item, context, onAdd, onClose }) {
  const variantList = Array.isArray(item.variants) ? item.variants : [];
  const baseSellable = variantList.length === 0 || item.base_sellable === undefined || !!item.base_sellable;
  const firstVariant = variantList.length
    ? typeof variantList[0] === "object"
      ? variantList[0]
      : { item: variantList[0], item_name: variantList[0], rate: 0 }
    : null;
  const [selectedVariant, setSelectedVariant] = useState(baseSellable ? null : firstVariant);
  const [selectedAddons, setSelectedAddons] = useState(new Set());
  const [notes, setNotes] = useState("");
  const [qty, setQty] = useState(1);

  // Start with the base item (no variant selected)
  const currentItem = selectedVariant || item;

  // P3-T5: When variant changes, reload its add-ons (merged with parent's)
  const currentVariants = Array.isArray(item.variants) ? item.variants : [];
  const currentAddons = selectedVariant
    ? [
        ...(Array.isArray(item.addons) ? item.addons : []),
        ...(Array.isArray(selectedVariant.addons) ? selectedVariant.addons : []),
      ]
    : (Array.isArray(item.addons) ? item.addons : []);

  // Calculate live total
  const itemTotal = currentItem.rate * qty;
  const addonsTotal = Array.from(selectedAddons).reduce((sum, addonItem) => {
    const addon = currentAddons.find((a) => (typeof a === "object" ? a.item === addonItem : a === addonItem));
    const rate = typeof addon === "object" ? addon.rate : 0;
    return sum + rate * qty;
  }, 0);
  const total = itemTotal + addonsTotal;

  function handleAdd() {
    onAdd(currentItem, qty, notes, selectedAddons, item.item);
    onClose();
  }

  function toggleAddon(addonItem) {
    const next = new Set(selectedAddons);
    if (next.has(addonItem)) {
      next.delete(addonItem);
    } else {
      next.add(addonItem);
    }
    setSelectedAddons(next);
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-nds-green rounded-lg max-w-3xl w-full max-h-[90vh] overflow-auto flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex p-5 border-b border-white/10">
          {/* Left: Image or placeholder */}
          <div className="shrink-0 mr-5">
            <ItemImage
              key={currentItem.item}
              image={currentItem.image || item.image}
              name={currentItem.item_name}
              className="w-32 h-32 rounded"
              textClass="text-4xl"
            />
          </div>

          {/* Middle: Name, notes, qty, variants */}
          <div className="flex-1">
            <h2 className="font-display text-2xl mb-1 break-words" data-testid="product-dialog-title">{item.item_name}</h2>
            <p className="text-sm text-nds-muted mb-3">
              {selectedVariant ? variantLabel(item.item_name, selectedVariant) : variantList.length ? "Regular" : "\u00a0"}
            </p>

            {/* Special instructions */}
            <textarea
              placeholder="Special instructions..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-white/5 border border-white/20 rounded px-3 py-2 mb-3 text-sm resize-none"
              rows={2}
            />

            {/* Quantity stepper */}
            <div className="flex items-center gap-2 mb-3">
              <button
                onClick={() => setQty(Math.max(1, qty - 1))}
                className="w-10 h-10 rounded bg-white/10 hover:bg-white/20 text-xl"
              >
                −
              </button>
              <span className="text-xl font-medium w-12 text-center">{qty}</span>
              <button
                onClick={() => setQty(qty + 1)}
                className="w-10 h-10 rounded bg-white/10 hover:bg-white/20 text-xl"
              >
                +
              </button>
            </div>

            {/* Variant buttons */}
            {currentVariants.length > 0 && (
              <div className="mb-3">
                <p className="text-sm text-nds-muted mb-2">Variants:</p>
                <div className="flex flex-wrap gap-2">
                  {baseSellable && (
                    <button
                      onClick={() => setSelectedVariant(null)}
                      className={`px-3 py-1.5 rounded text-sm ${
                        !selectedVariant
                          ? "bg-nds-accent text-nds-green"
                          : "bg-white/10 hover:bg-white/20"
                      }`}
                    >
                      Regular ({item.rate})
                    </button>
                  )}
                  {currentVariants.map((v) => {
                    const variantItem = typeof v === "object" ? v.item : v;
                    const variantName = variantLabel(item.item_name, v);
                    const variantRate = typeof v === "object" ? v.rate : 0;
                    const isSelected = selectedVariant && (typeof selectedVariant === "object" ? selectedVariant.item === variantItem : selectedVariant === variantItem);
                    return (
                      <button
                        key={variantItem}
                        onClick={() => setSelectedVariant(typeof v === "object" ? v : { item: v, item_name: v, rate: 0 })}
                        className={`px-3 py-1.5 rounded text-sm ${
                          isSelected
                            ? "bg-nds-accent text-nds-green"
                            : "bg-white/10 hover:bg-white/20"
                        }`}
                      >
                        {variantName} ({variantRate})
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right: Live total and Add button */}
          <div className="shrink-0 ml-5 flex flex-col items-end">
            <div className="text-3xl font-display text-nds-accent mb-4">{total.toFixed(2)}</div>
            <button
              onClick={handleAdd}
              className="px-6 py-3 rounded bg-nds-accent text-nds-green font-medium hover:opacity-90"
            >
              Add to Order
            </button>
          </div>
        </div>

        {/* Add-ons section */}
        {currentAddons.length > 0 && (
          <div className="p-5">
            <p className="text-sm text-nds-muted mb-3">Add-ons:</p>
            <div className="space-y-2">
              {currentAddons.map((addon) => {
                const addonItem = typeof addon === "object" ? addon.item : addon;
                const addonName = typeof addon === "object" ? addon.item_name : addon;
                const addonRate = typeof addon === "object" ? addon.rate : 0;
                const isChecked = selectedAddons.has(addonItem);
                return (
                  <button
                    key={addonItem}
                    onClick={() => toggleAddon(addonItem)}
                    className={`w-full text-left px-4 py-2 rounded border ${
                      isChecked
                        ? "bg-nds-accent/20 border-nds-accent"
                        : "bg-white/5 border-white/10 hover:border-white/30"
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span>{addonName}</span>
                      <span className="text-sm text-nds-accent">+{addonRate}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="p-5 border-t border-white/10 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded bg-white/10 hover:bg-white/20"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
