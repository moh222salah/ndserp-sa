import React from "react";
import { usePOSStore } from "../store";

export default function TablesView({ tables }) {
  const { setSelectedTable, selectedTable } = usePOSStore();

  const handleTableClick = async (tableName) => {

    await setSelectedTable(tableName);
  };

  return (
    <div className="flex-1 p-6 text-white overflow-y-auto">
      <h2 className="font-display text-2xl mb-4">Select a table</h2>

      <div className="grid grid-cols-4 gap-4">
        {(tables || []).map((t) => {
          const isSelected = selectedTable === t.name;
          const isOccupied = t.occupied;

          return (
            <button
              key={t.name}
              onClick={() => handleTableClick(t.name)}
              className={`p-6 rounded-xl border text-left transition relative flex flex-col justify-between h-36 ${
                isOccupied
                  ? "bg-amber-950/40 border-amber-600/60 hover:bg-amber-900/50"
                  : isSelected
                  ? "bg-emerald-950/40 border-emerald-500"
                  : "bg-black/20 border-white/10 hover:bg-white/10"
              }`}
            >
              <div>
                <p className="font-display text-xl font-bold">{t.name}</p>
                <p className="text-xs text-gray-400">{t.seats || 4} seats</p>
              </div>

              <div className="flex justify-between items-center">
                <span
                  className={`text-xs px-2 py-0.5 rounded font-semibold ${
                    isOccupied ? "bg-amber-500/20 text-amber-400" : "text-emerald-400"
                  }`}
                >
                  {isOccupied ? "Occupied" : "Free"}
                </span>
                {t.current_invoice && (
                  <span className="text-[10px] text-gray-400 truncate max-w-[100px]">
                    {t.current_invoice}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}