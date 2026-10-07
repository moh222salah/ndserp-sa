import React, { useState } from "react";

export function initials(name) {
  return (name || "")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase();
}

// Image with an initials placeholder when there is no image or it fails to load.
export function ItemImage({ image, name, className = "", textClass = "text-2xl" }) {
  const [failed, setFailed] = useState(false);
  if (image && !failed) {
    return (
      <img
        src={encodeURI(image)}
        alt=""
        loading="lazy"
        className={`${className} max-w-full object-cover`}
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <div className={`${className} bg-white/5 flex items-center justify-center font-display text-white/40 ${textClass}`}>
      {initials(name)}
    </div>
  );
}

function getStockBadge(availability, lowStockThreshold) {
  if (availability === null || availability === undefined) return null;
  if (availability > lowStockThreshold) {
    return { color: "bg-green-600", text: availability };
  }
  if (availability > 0) {
    return { color: "bg-orange-600", text: availability };
  }
  return { color: "bg-red-600", text: "0" };
}

export default function MenuView({
  courses,
  items,
  courseFilter,
  setCourseFilter,
  onItemClick,
  context,
  orderType,
  selectedTable,
  lowStockThreshold = 5,
}) {
  return (
    <>
      <aside className="w-32 lg:w-40 shrink-0 border-r border-white/10 p-3 space-y-1 overflow-auto bg-black/15">
        <button
          onClick={() => setCourseFilter(null)}
          className={`w-full text-left px-3 py-2 rounded text-sm ${
            !courseFilter ? "bg-nds-accent/30" : "hover:bg-white/10"
          }`}
        >
          All
        </button>
        <button
          onClick={() => setCourseFilter("__specials__")}
          className={`w-full text-left px-3 py-2 rounded text-sm ${
            courseFilter === "__specials__" ? "bg-nds-accent/30" : "hover:bg-white/10"
          }`}
        >
          ★ Specials
        </button>
        {courses.map((c) => (
          <button
            key={c.name}
            onClick={() => setCourseFilter(c.name)}
            className={`w-full text-left px-3 py-2 rounded text-sm ${
              courseFilter === c.name ? "bg-nds-accent/30" : "hover:bg-white/10"
            }`}
          >
            {c.course || c.name}
          </button>
        ))}
      </aside>
      <div className="flex-1 min-w-0 p-3 lg:p-4 overflow-y-auto overflow-x-hidden">
        <div className="mb-3 text-sm text-nds-muted">
          {orderType}
          {selectedTable ? ` · ${selectedTable}` : ""}
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
          {items.map((item) => {
            const stockBadge = getStockBadge(item.availability, lowStockThreshold);
            const isDisabled = item.availability === 0;
            return (
              <button
                key={item.item}
                type="button"
                onClick={() => !isDisabled && onItemClick(item)}
                disabled={isDisabled}
                className={`relative min-w-0 overflow-hidden text-left p-3 rounded-lg bg-white/5 border border-white/10 hover:border-nds-accent transition ${
                  isDisabled ? "opacity-40 cursor-not-allowed" : ""
                }`}
              >
                {!!item.special_dish && (
                  <div className="absolute top-0 right-0 bg-nds-accent text-nds-green text-xs font-bold px-2 py-1 rounded-bl">
                    ★ Special
                  </div>
                )}
                {context.settings?.show_item_image ? (
                  <ItemImage image={item.image} name={item.item_name} className="w-full h-24 rounded mb-2" textClass="text-2xl" />
                ) : null}
                <div className="font-medium break-words">{item.item_name}</div>
                <div className="flex justify-between text-sm mt-1">
                  <span className="text-nds-accent">{item.rate}</span>
                  {stockBadge && (
                    <span className={`${stockBadge.color} text-white px-2 py-0.5 rounded text-xs font-medium`}>
                      {stockBadge.text}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
