import React, { useState, useEffect, useRef, useLayoutEffect, useMemo } from "react";
import { usePOSStore, UNASSIGNED_ROOM } from "../store";
import { parseSiteDateTime } from "../lib/datetime";
import { showUserAlert } from "../lib/errors";

function shortUser(u) {
  return u ? String(u).split("@")[0] : "";
}

// P4-T3: a table held by another captain is locked for restricted users.
function openTable(table, setSelectedTable) {
  if (table.locked) {
    showUserAlert(`Table ${table.name} belongs to ${table.captain}`);
    return;
  }
  setSelectedTable(table.name);
}

export default function FloorPlan() {
  const { context, setSelectedTable, refreshContext } = usePOSStore();
  const rooms = context?.rooms || [];
  const tables = context?.tables || [];
  const attentionTimeLimit = context?.settings?.table_attention_time || 0;
  const timeZone = context?.time_zone;

  const hasUnassigned = tables.some((t) => !t.restaurant_room);
  const roomTabs = useMemo(() => {
    const tabs = rooms.map((r) => ({ name: r.name, room_type: r.room_type }));
    if (hasUnassigned) {
      tabs.push({ name: UNASSIGNED_ROOM, room_type: "" });
    }
    return tabs;
  }, [rooms, hasUnassigned]);

  const defaultRoom = roomTabs.length > 0 ? roomTabs[0].name : UNASSIGNED_ROOM;
  const [activeRoom, setActiveRoom] = useState(defaultRoom);
  const [currentTime, setCurrentTime] = useState(new Date());
  const planRef = useRef(null);
  const [planScale, setPlanScale] = useState(1);

  useEffect(() => {
    if (roomTabs.length > 0 && !roomTabs.find((r) => r.name === activeRoom)) {
      setActiveRoom(roomTabs[0].name);
    }
  }, [roomTabs, activeRoom]);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
      refreshContext();
    }, 30000);
    return () => clearInterval(interval);
  }, [refreshContext]);

  const roomTables = tables.filter((t) => {
    const roomKey = t.restaurant_room || UNASSIGNED_ROOM;
    return roomKey === activeRoom;
  });

  const isGridFallback = roomTables.every(
    (t) => !t.layout_x && !t.layout_y && !t.layout_width && !t.layout_height
  );

  const layoutBounds = useMemo(() => {
    if (isGridFallback) return null;
    let maxX = 0;
    let maxY = 0;
    roomTables.forEach((t) => {
      const x = (t.layout_x || 0) + (t.layout_width || 100);
      const y = (t.layout_y || 0) + (t.layout_height || 100);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    });
    return { width: maxX + 20, height: maxY + 20 };
  }, [roomTables, isGridFallback]);

  useLayoutEffect(() => {
    if (!planRef.current || !layoutBounds) {
      setPlanScale(1);
      return;
    }
    const el = planRef.current;
    const availableW = el.clientWidth - 32;
    const availableH = el.clientHeight - 32;
    if (availableW <= 0 || availableH <= 0) return;
    const scale = Math.min(1, availableW / layoutBounds.width, availableH / layoutBounds.height);
    setPlanScale(scale);
  }, [layoutBounds, activeRoom, roomTables.length]);

  const needsAttention = (table) => {
    if (!table.occupied || attentionTimeLimit <= 0 || !table.latest_invoice_time) return false;

    const latestTime = parseSiteDateTime(table.latest_invoice_time, timeZone);
    if (!latestTime) return false;
    const diffInMinutes = (currentTime.getTime() - latestTime.getTime()) / (1000 * 60);

    return diffInMinutes >= attentionTimeLimit;
  };

  return (
    <div className="flex flex-col h-full w-full p-4 bg-gray-50">
      {roomTabs.length > 0 && (
        <div className="flex space-x-2 border-b border-gray-300 mb-4 pb-2">
          {roomTabs.map((room) => (
            <button
              key={room.name}
              onClick={() => setActiveRoom(room.name)}
              className={`px-6 py-2 rounded-t-lg font-semibold transition-colors ${
                activeRoom === room.name
                  ? "bg-green-700 text-white shadow-md"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }`}
            >
              {room.name}
            </button>
          ))}
        </div>
      )}

      <div
        ref={planRef}
        className={`flex-1 relative overflow-auto p-4 ${
          isGridFallback ? "grid grid-cols-2 md:grid-cols-4 gap-4" : "bg-white border rounded-lg shadow-inner min-h-[600px]"
        }`}
      >
        {!isGridFallback && layoutBounds && (
          <div
            style={{
              position: "relative",
              width: layoutBounds.width,
              height: layoutBounds.height,
              transform: `scale(${planScale})`,
              transformOrigin: "top left",
            }}
          >
            {roomTables.map((table) => renderTable(table, false, needsAttention, setSelectedTable))}
          </div>
        )}
        {isGridFallback && roomTables.map((table) => renderTable(table, true, needsAttention, setSelectedTable))}
      </div>
    </div>
  );
}

function renderTable(table, isGridFallback, needsAttention, setSelectedTable) {
  const isOccupied = table.occupied;
  const isCircle = table.table_shape === "Circle" || table.table_shape === "Round";
  const alertAttention = needsAttention(table);

  if (isGridFallback) {
    return (
      <div
        key={table.name}
        onClick={() => openTable(table, setSelectedTable)}
        role="button"
        aria-label={`Table ${table.name}, ${isOccupied ? "Occupied" : "Free"}${table.locked ? ", locked" : ""}${table.ready ? ", ready" : ""}`}
        data-locked={table.locked ? "1" : "0"}
        className={`relative p-6 rounded-lg cursor-pointer flex flex-col items-center justify-center shadow-md transition-transform hover:scale-105 min-h-[120px] ${
          isOccupied ? "bg-red-100 text-red-900 border border-red-300" : "bg-white text-green-900 border border-green-300"
        }`}
      >
        {alertAttention && (
          <span className="absolute -top-2 -right-2 bg-red-600 text-white text-xs px-2 py-1 rounded-full animate-pulse shadow-lg font-bold">
            Attention
          </span>
        )}
        {table.ready ? (
          <span
            className="absolute -top-2 -left-2 bg-emerald-600 text-white text-xs px-2 py-1 rounded-full shadow-lg font-bold"
            data-testid="table-ready"
          >
            Ready
          </span>
        ) : null}
        <span className="text-xl font-bold">{table.name}</span>
        <span className="text-sm opacity-75">{table.no_of_seats} seats</span>
        <span className="text-xs mt-2 font-semibold">
          {table.locked ? "🔒 " : ""}
          {isOccupied ? "Occupied" : "Free"}
        </span>
        {isOccupied && table.captain && (
          <span className="text-[11px] opacity-75 truncate max-w-full" data-testid="table-captain">
            {shortUser(table.captain)}
          </span>
        )}
      </div>
    );
  }

  const absoluteStyle = {
    position: "absolute",
    left: `${table.layout_x || 0}px`,
    top: `${table.layout_y || 0}px`,
    width: `${table.layout_width || 100}px`,
    height: `${table.layout_height || 100}px`,
    borderRadius: isCircle ? "50%" : "12px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "transform 0.2s",
    boxShadow: alertAttention ? "0 0 15px rgba(220, 38, 38, 0.6)" : "0 4px 6px rgba(0, 0, 0, 0.1)",
    backgroundColor: isOccupied ? "#fee2e2" : "#ffffff",
    border: alertAttention ? "3px solid #dc2626" : isOccupied ? "2px solid #ef4444" : "2px solid #22c55e",
  };

  return (
    <div
      key={table.name}
      style={absoluteStyle}
      onClick={() => openTable(table, setSelectedTable)}
      role="button"
      aria-label={`Table ${table.name}, ${isOccupied ? "Occupied" : "Free"}${table.locked ? ", locked" : ""}${table.ready ? ", ready" : ""}`}
      data-locked={table.locked ? "1" : "0"}
      className={`hover:scale-105 ${alertAttention ? "animate-pulse" : ""}`}
    >
      {alertAttention && (
        <span className="absolute -top-3 bg-red-600 text-white text-[10px] px-2 py-0.5 rounded-full shadow-lg font-bold">
          Attention
        </span>
      )}
      {table.ready ? (
        <span
          className="absolute -bottom-3 bg-emerald-600 text-white text-[10px] px-2 py-0.5 rounded-full shadow-lg font-bold"
          data-testid="table-ready"
        >
          Ready
        </span>
      ) : null}
      <span className="text-lg font-bold text-gray-800">{table.name}</span>
      <span className="text-xs text-gray-600">{table.no_of_seats} seats</span>
      <span
        className={`mt-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
          isOccupied ? "bg-red-600 text-white" : "bg-green-600 text-white"
        }`}
      >
        {table.locked ? "🔒 " : ""}
        {isOccupied ? "Occupied" : "Free"}
      </span>
      {isOccupied && table.captain && (
        <span className="text-[10px] text-gray-600 truncate max-w-full px-1" data-testid="table-captain">
          {shortUser(table.captain)}
        </span>
      )}
    </div>
  );
}
