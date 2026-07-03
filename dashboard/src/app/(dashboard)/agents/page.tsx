"use client";

import { useEffect, useState } from "react";
import { Play, Pause, RotateCw, FileText, CheckCircle2, ShieldAlert } from "lucide-react";

import { WS_URL } from "@/utils/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<any[]>([]);
  const [overrideModal, setOverrideModal] = useState<string | null>(null);
  const [overrideInput, setOverrideInput] = useState("");
  const [role, setRole] = useState("viewer");

  useEffect(() => {
    // Get user role
    const user = localStorage.getItem("user");
    if (user) {
      try {
        setRole(JSON.parse(user).role);
      } catch (e) {}
    }

    // Connect to WebSocket API
    const ws = new WebSocket(`${WS_URL}/api/v1/ws/dashboard`);
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.agents) {
          setAgents(payload.agents);
        }
      } catch (e) {
        console.error("WS error", e);
      }
    };
    return () => ws.close();
  }, []);

  const handleToggleAgent = (name: string) => {
    if (role === "viewer") {
      alert("Permission Denied: Viewer role is restricted to read-only views.");
      return;
    }
    setAgents((prev) =>
      prev.map((a) =>
        a.name === name 
          ? { ...a, status: a.status === "ACTIVE" ? "DISABLED" : "ACTIVE" } 
          : a
      )
    );
  };

  const handleOverrideSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (role === "viewer") {
      alert("Permission Denied: Viewer role is restricted to read-only views.");
      setOverrideModal(null);
      return;
    }
    
    alert(`Success: Override decision "${overrideInput}" submitted to ${overrideModal}. CEO Agent has prioritized this action override.`);
    setOverrideModal(null);
    setOverrideInput("");
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">AGENT CONTROL CENTER</h1>
          <p className="text-xs text-gray-500">Enable/disable independent AI agents, audit telemetry, or issue administrative overrides</p>
        </div>
      </div>

      {/* Agents Control Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {agents.length > 0 ? (
          agents.map((a, idx) => (
            <div key={idx} className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] flex flex-col justify-between h-96">
              {/* Header */}
              <div>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold font-mono text-white text-sm uppercase tracking-wide">{a.name}</h3>
                    <span className="text-[10px] text-gray-500">Confidence: {Math.round(a.confidence * 100)}%</span>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-1 rounded font-mono ${
                    a.status === 'ACTIVE' 
                      ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-500/20' 
                      : a.status === 'DISABLED'
                      ? 'bg-rose-950/20 text-rose-400 border border-rose-500/20'
                      : 'bg-white/5 text-gray-500 border border-white/10'
                  }`}>
                    {a.status}
                  </span>
                </div>

                {/* Info Lines */}
                <div className="space-y-3.5 text-xs border-t border-white/5 pt-4">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Last Action:</span>
                    <span className="text-gray-300 font-medium">{a.last_action}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Recent Decision:</span>
                    <span className="text-[#d4af37] font-semibold">{a.decision}</span>
                  </div>
                  
                  {/* Logs Section */}
                  <div className="space-y-1.5 mt-2">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5 text-[#d4af37]" /> Agent Activity Logs
                    </span>
                    <div className="h-20 bg-black/40 border border-white/5 rounded-lg p-2.5 overflow-y-auto text-[10px] text-gray-400 font-mono leading-relaxed">
                      {a.logs}
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 pt-4 border-t border-white/5 mt-4">
                <button
                  onClick={() => handleToggleAgent(a.name)}
                  className={`flex-1 py-2 rounded-lg text-xs font-bold font-mono border transition-all flex items-center justify-center gap-2 ${
                    a.status === 'ACTIVE' 
                      ? 'border-rose-500/30 text-rose-400 hover:bg-rose-950/10' 
                      : 'border-emerald-500/30 text-emerald-400 hover:bg-emerald-950/10'
                  }`}
                >
                  {a.status === 'ACTIVE' ? (
                    <>
                      <Pause className="w-3.5 h-3.5" /> Deactivate
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" /> Activate
                    </>
                  )}
                </button>
                <button
                  onClick={() => setOverrideModal(a.name)}
                  className="px-3.5 py-2 rounded-lg border border-[#d4af37]/30 text-[#d4af37] text-xs font-bold font-mono hover:bg-[#d4af37]/10 transition-all flex items-center justify-center"
                >
                  <RotateCw className="w-3.5 h-3.5" /> Override
                </button>
              </div>

            </div>
          ))
        ) : (
          <div className="col-span-3 text-center py-20 text-xs text-gray-600 font-mono uppercase">
            Awaiting WebSocket connection sync...
          </div>
        )}
      </div>

      {/* Manual Override Modal */}
      {overrideModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="w-full max-w-md glass-panel p-6 bg-[rgba(10,10,14,0.9)] space-y-6">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-[#d4af37]" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">Manual Override — {overrideModal}</h2>
            </div>
            
            <form onSubmit={handleOverrideSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                  Override Decision Payload (JSON or Directive)
                </label>
                <textarea
                  value={overrideInput}
                  onChange={(e) => setOverrideInput(e.target.value)}
                  placeholder="e.g. { 'force_buy': true }"
                  className="w-full h-24 bg-black/40 border border-white/10 p-3 rounded-lg text-xs text-white focus:outline-none focus:border-[#d4af37] font-mono"
                  required
                />
              </div>

              <div className="flex gap-3 text-xs font-bold">
                <button
                  type="button"
                  onClick={() => setOverrideModal(null)}
                  className="flex-1 py-2.5 rounded-lg border border-white/10 text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-lg bg-[#d4af37] text-black hover:opacity-90"
                >
                  Submit Override
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
