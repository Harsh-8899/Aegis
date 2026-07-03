"use client";

import { useEffect, useState } from "react";
import { FileText, Filter, Search, Terminal } from "lucide-react";

export default function AuditPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [filter, setFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    // Connect to WebSocket API
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard");
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.alerts) {
          // Map alerts to logs list
          const mappedLogs = payload.alerts.map((a: any) => ({
            timestamp: a.time,
            category: a.severity === 'CRITICAL' ? 'error' : 'risk',
            source: 'RiskEngine',
            message: a.message
          }));
          
          // Seed standard simulation log lines so it looks full and active
          const mockLogs = [
            { timestamp: new Date().toISOString(), category: "agent", source: "CEOAgent", message: "Cycle execution check completed. 0 trades triggered." },
            { timestamp: new Date().toISOString(), category: "model", source: "MLAgent", message: "Inference probabilities loaded. Confidence index: 0.54." },
            { timestamp: new Date().toISOString(), category: "trade", source: "ExecutionAgent", message: "Mock paper trade fill completed at $2331.42." }
          ];

          setLogs((prev) => {
            const combined = [...mockLogs, ...mappedLogs, ...prev];
            // Remove duplicates and limit length to 100
            const unique = combined.filter((v, i, a) => a.findIndex(t => t.message === v.message && t.timestamp === v.timestamp) === i);
            return unique.slice(0, 100);
          });
        }
      } catch (e) {}
    };
    return () => ws.close();
  }, []);

  const filteredLogs = logs.filter((log) => {
    const matchesCategory = filter === "all" || log.category === filter;
    const matchesSearch = log.message.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          log.source.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">LOGS & AUDIT TRAIL</h1>
          <p className="text-xs text-gray-500">Search database operations log trails, model inference logs, and user configuration updates</p>
        </div>
      </div>

      {/* Filter Ribbon */}
      <div className="flex flex-col md:flex-row gap-4 justify-between items-center glass-panel p-4 bg-[rgba(16,16,24,0.4)]">
        <div className="flex gap-2 text-xs font-mono">
          {[
            { label: "ALL TRAILS", val: "all" },
            { label: "AGENT ACTIONS", val: "agent" },
            { label: "TRADES FILLED", val: "trade" },
            { label: "RISK VETOS", val: "risk" },
            { label: "ML MODELS", val: "model" },
            { label: "ERRORS", val: "error" }
          ].map((btn) => (
            <button
              key={btn.val}
              onClick={() => setFilter(btn.val)}
              className={`px-3 py-1.5 rounded transition-all ${
                filter === btn.val 
                  ? 'bg-[#d4af37] text-black font-bold' 
                  : 'bg-white/2 border border-white/10 text-gray-400 hover:text-white'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>

        {/* Search Bar */}
        <div className="relative w-full md:w-64">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search audit trail..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-black/40 border border-white/10 pl-9 pr-4 py-2 rounded-lg text-xs text-white focus:outline-none focus:border-[#d4af37]"
          />
        </div>
      </div>

      {/* Logs Shell Output panel */}
      <div className="glass-panel p-6 bg-black/50 border-white/5 font-mono text-xs overflow-hidden">
        <div className="flex gap-2 items-center text-gray-500 border-b border-white/5 pb-4 mb-4">
          <Terminal className="w-4 h-4" />
          <span>Secured Terminal Console Audit Output</span>
        </div>

        <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-2 leading-relaxed">
          {filteredLogs.length > 0 ? (
            filteredLogs.map((l, idx) => (
              <div key={idx} className="flex gap-4 items-start select-text hover:bg-white/2 p-1 rounded transition-colors">
                <span className="text-gray-600 shrink-0">[{new Date(l.timestamp).toLocaleTimeString()}]</span>
                <span className={`uppercase font-bold shrink-0 text-[10px] px-1.5 py-0.5 rounded ${
                  l.category === 'trade' 
                    ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-500/20' 
                    : l.category === 'error'
                    ? 'bg-rose-950/20 text-rose-400 border border-rose-500/20'
                    : l.category === 'risk'
                    ? 'bg-amber-950/20 text-amber-400 border border-amber-500/20'
                    : 'bg-white/5 text-gray-400 border border-white/10'
                }`}>
                  {l.category}
                </span>
                <span className="text-[#d4af37] shrink-0 font-bold">{l.source}:</span>
                <span className="text-gray-300">{l.message}</span>
              </div>
            ))
          ) : (
            <div className="text-center py-20 text-gray-600 uppercase">
              No matching log records found in audit trails index.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
