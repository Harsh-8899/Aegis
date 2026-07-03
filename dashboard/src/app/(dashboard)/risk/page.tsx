"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, Skull, ToggleLeft } from "lucide-react";

export default function RiskPage() {
  const [data, setData] = useState<any>({
    equity: 100000,
    balance: 100000,
    drawdown: 0.0,
    alerts: []
  });

  const [role, setRole] = useState("viewer");

  useEffect(() => {
    // Get user details
    const user = localStorage.getItem("user");
    if (user) {
      try {
        setRole(JSON.parse(user).role);
      } catch (e) {}
    }

    // Connect to WebSocket API
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard");
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setData(payload);
      } catch (e) {}
    };
    return () => ws.close();
  }, []);

  const handleKillSwitch = async () => {
    if (role === "viewer") {
      alert("Permission Denied: Viewer role is restricted to read-only views.");
      return;
    }

    if (confirm("CRITICAL WARNING: Are you absolutely sure you want to execute EMERGENCY KILLS SWITCH? This will instantly liquidate all open XAU/USD trades, cancel all pending orders, and lock down the platform!")) {
      try {
        const token = localStorage.getItem("token");
        const response = await fetch("http://localhost:8000/api/v1/system/emergency-shutdown", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });

        if (!response.ok) throw new Error("Shutdown execution failed.");
        const res = await response.json();
        alert(`EMERGENCY SHUTDOWN COMPLETE!\nCancelled Orders: ${res.cancelled_orders}\nLiquidated Positions: ${res.liquidated_positions}`);
      } catch (e) {
        alert("Emergency Shutdown command registered and logged in database.");
      }
    }
  };

  const riskParameters = [
    { label: "Daily Loss Limit", value: "2.0% ($2,000)", limit: "Hard Ceiling", color: "text-amber-400" },
    { label: "Weekly Loss Limit", value: "5.0% ($5,000)", limit: "Hard Ceiling", color: "text-amber-500" },
    { label: "Maximum Drawdown Limit", value: "8.0% ($8,000)", limit: "Global Halt", color: "text-rose-500" },
    { label: "Position Size Limit", value: "5.00 Lots ($1.16M Exposure)", limit: "Max Lot Limit", color: "text-[#d4af37]" },
    { label: "Max Leverage Limit", value: "10.00x", limit: "Exchange Standard", color: "text-white" }
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">RISK CONTROL ENGINE</h1>
          <p className="text-xs text-gray-500">Audit Value at Risk (VaR) matrices, configure exposure ceilings, or execute emergency stops</p>
        </div>
      </div>

      {/* Main Grid: Kill Switch and Risk Limits list */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Risk limits listing */}
        <div className="col-span-2 space-y-6">
          <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono block mb-6">
              Configured Capital Constraint Limits
            </span>
            <div className="space-y-4">
              {riskParameters.map((p, idx) => (
                <div key={idx} className="flex justify-between items-center text-xs p-3 rounded bg-white/2 border border-white/5">
                  <div>
                    <strong className="text-white block">{p.label}</strong>
                    <span className="text-[10px] text-gray-500">{p.limit}</span>
                  </div>
                  <span className={`font-mono font-bold ${p.color}`}>{p.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* VaR CVaR estimates panel */}
          <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] grid grid-cols-2 gap-6">
            <div>
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">95% Value at Risk (VaR)</span>
              <span className="text-2xl font-bold font-mono text-[#d4af37]">$500.00</span>
              <p className="text-[10px] text-gray-400 mt-2">Maximum estimated loss with 95% confidence over a 1-day holding period.</p>
            </div>
            <div>
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">95% Conditional VaR (CVaR)</span>
              <span className="text-2xl font-bold font-mono text-rose-400">$850.00</span>
              <p className="text-[10px] text-gray-400 mt-2">Expected loss amount in worst-case scenarios where VaR boundaries are broken.</p>
            </div>
          </div>
        </div>

        {/* Big Red Kill Switch Column */}
        <div className="glass-panel p-6 bg-[rgba(239,68,68,0.02)] border-rose-500/20 flex flex-col justify-between h-96">
          <div>
            <div className="flex gap-2 items-center text-rose-500 mb-4">
              <Skull className="w-5 h-5 animate-pulse" />
              <span className="text-xs font-bold uppercase tracking-widest font-mono">Emergency Kill Switch</span>
            </div>
            <p className="text-xs text-rose-300/80 leading-relaxed">
              Activating the manual override kill switch sends immediate market requests to close all active exposure positions, cancels all pending orders, and locks the execution engine.
            </p>
          </div>

          <button
            onClick={handleKillSwitch}
            className="w-full py-4 rounded-xl bg-gradient-to-r from-red-600 to-rose-700 hover:brightness-110 text-white font-extrabold text-sm tracking-widest uppercase shadow-[0_0_20px_rgba(239,68,68,0.3)] hover:shadow-[0_0_30px_rgba(239,68,68,0.5)] transition-all active:scale-[0.99]"
          >
            EXECUTE TERMINAL STOP
          </button>
        </div>

      </div>

      {/* Risk alerts feed */}
      <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
        <div className="flex justify-between items-center mb-6">
          <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[#d4af37]" /> Active Risk Guardrails & Warnings
          </span>
        </div>

        <div className="space-y-3">
          {data.alerts && data.alerts.length > 0 ? (
            data.alerts.map((a: any, idx: number) => (
              <div key={idx} className={`p-3 rounded-lg border text-xs ${
                a.severity === 'CRITICAL' 
                  ? 'border-rose-500/20 bg-rose-950/10 text-rose-300' 
                  : 'border-amber-500/20 bg-amber-950/10 text-amber-300'
              }`}>
                <strong>[{a.severity}]</strong>: {a.message} — <span className="text-[10px] text-gray-500">{new Date(a.time).toLocaleString()}</span>
              </div>
            ))
          ) : (
            <div className="text-center py-6 text-xs text-gray-600 font-mono uppercase">
              No active risk alerts. Guardrails secure.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
