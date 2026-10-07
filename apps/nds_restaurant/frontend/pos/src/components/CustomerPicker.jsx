import { useState, useEffect } from "react";
import { searchCustomers, createCustomer } from "../api";
import { usePOSStore } from "../store";

export default function CustomerPicker() {
  const { customer, setCustomer } = usePOSStore();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newMobile, setNewMobile] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.trim().length > 1) {
      const timer = setTimeout(async () => {
        try {
          const res = await searchCustomers(query);
  
          const list = res && res.message ? res.message : Array.isArray(res) ? res : [];
          setResults(list);
        } catch (err) {
          console.error("Search customer error:", err);
          setResults([]);
        }
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setResults([]);
    }
  }, [query]);

  async function handleCreate(e) {
    e.preventDefault();
    if (!newName || !newMobile) return alert("Name and Mobile are required");
    setLoading(true);
    try {
      const res = await createCustomer(newName, newMobile);
      const data = res.message || res;
      if (data.name) {
        setCustomer(data);
        setShowNewForm(false);
        setNewName("");
        setNewMobile("");
        setQuery("");
      } else if (data.exc || data.error) {
        alert("Error: " + (data.error || "Failed to create customer"));
      }
    } catch (err) {
      alert("Failed to create customer");
    }
    setLoading(false);
  }

  if (customer) {
    return (
      <div className="flex items-center justify-between bg-emerald-900/40 border border-emerald-500/50 p-2.5 rounded-lg mb-3">
        <div>
          <p className="text-sm text-emerald-400 font-semibold">{customer.customer_name}</p>
          <p className="text-xs text-gray-300">{customer.mobile_no || customer.mobile_number || "Walk-in"}</p>
        </div>
        <button 
          onClick={() => setCustomer(null)} 
          className="text-red-400 hover:text-red-300 text-xs px-2 py-1 bg-red-950/40 rounded border border-red-800/40"
        >
          Remove
        </button>
      </div>
    );
  }

  if (showNewForm) {
    return (
      <form onSubmit={handleCreate} className="bg-gray-900 p-3 rounded-lg border border-gray-700 mb-3 text-white shadow-lg">
        <p className="text-sm mb-2 font-semibold text-white">Create New Customer</p>
        <input 
          type="text" 
          placeholder="Customer Name" 
          value={newName} 
          onChange={(e) => setNewName(e.target.value)} 
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm mb-2 text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500" 
          autoFocus 
        />
        <input 
          type="tel" 
          placeholder="Mobile Number" 
          value={newMobile} 
          onChange={(e) => setNewMobile(e.target.value)} 
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm mb-2 text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500" 
        />
        <div className="flex gap-2 mt-1">
          <button 
            type="submit" 
            disabled={loading} 
            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold py-1.5 rounded transition"
          >
            {loading ? "Saving..." : "Save Customer"}
          </button>
          <button 
            type="button" 
            onClick={() => setShowNewForm(false)} 
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-white text-sm py-1.5 rounded transition"
          >
            Cancel
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="relative mb-3">
      <input
        type="text"
        placeholder="Search customer (Name or Mobile)..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500"
      />
      
      {results.length > 0 && (
        <div className="absolute top-full left-0 w-full mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl z-30 max-h-48 overflow-y-auto">
          {results.map((r) => (
            <div 
              key={r.name} 
              onClick={() => { setCustomer(r); setQuery(""); setResults([]); }} 
              className="p-2.5 border-b border-gray-800 hover:bg-gray-800 cursor-pointer text-white transition"
            >
              <p className="text-sm font-medium text-white">{r.customer_name}</p>
              <p className="text-xs text-gray-400">{r.mobile_no || r.mobile_number || r.name}</p>
            </div>
          ))}
          <div 
            onClick={() => { setShowNewForm(true); setNewName(query); setResults([]); }} 
            className="p-2.5 text-center text-emerald-400 hover:bg-gray-800 cursor-pointer text-sm font-bold border-t border-gray-800"
          >
            + Add New Customer
          </div>
        </div>
      )}

      {query.trim().length > 1 && results.length === 0 && (
        <div className="absolute top-full left-0 w-full mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl z-30 p-3 text-white">
          <p className="text-xs text-center text-gray-300 mb-2 font-medium">No results found for "{query}"</p>
          <button 
            onClick={() => { setShowNewForm(true); setNewName(query); }} 
            className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-md text-sm transition shadow"
          >
            + Create "{query}"
          </button>
        </div>
      )}
    </div>
  );
}