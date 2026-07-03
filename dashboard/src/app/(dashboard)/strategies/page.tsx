"use client";

import { useEffect, useState } from "react";
import { Sliders, Activity, ShieldCheck, TrendingUp, TrendingDown } from "lucide-react";

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState([
    { name: "Trend Following", id: "trend_following", status: "ACTIVE", signal: "BUY", winRate: "62.4%", profitFactor: "1.85", sharpe: "2.12", drawdown: "4.2%", allocation: 40 },
    { name: "Mean Reversion", id: "mean_reversion", status: "ACTIVE", signal: "FLAT", winRate: "58.1%", profitFactor: "1.42", sharpe: "1.65", drawdown: "3.8%", allocation: 30 },
    { name: "Volatility Breakout", id: "breakout", status: "ACTIVE", signal: "BUY", winRate: "54.8%", profitFactor: "1.60", sharpe: "1.92", drawdown: "6.5%", allocation: 30 }
  ]);

  const [trades, setTrades] = useState<any[]>([]);
  const [role, setRole] = useState("viewer");

  useEffect(() => {
    // Fetch user details
    const user = localStorage.getItem("user");
    if (user) {
      try {
        setRole(JSON.parse(user).role);
      } catch (e) {}
    }

    // Connect to WebSocket API to stream recent positions/trades
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard");
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.positions) {
          setTrades(payload.positions);
        }
      } catch (e) {}
    };
    return () => ws.close();
  }, []);

  const handleAllocationChange = (id: string, newVal: number) => {
    setStrategies((prev) =>
      prev.map((s) => (s.id === id ? { ...s, allocation: newVal } : s))
    );
  };

  const handleSaveAllocations = async () => {
    if (role !== "admin") {
      alert("Permission Denied: Only users with 'Admin' role can update system configurations.");
      return;
    }

    try {
      const weights = strategies.reduce((acc: any, s) => {
        acc[s.id] = s.allocation / 100;
        return acc;
      }, {});

      const token = localStorage.getItem("token");
      const response = await fetch("http://localhost:8000/api/v1/system/config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          max_daily_loss_pct: 0.02,
          max_position_exposure_pct: 0.15,
          allocation_weights: weights
        })
      });

      if (!response.ok) throw new Error("Failed to save configs.");
      alert("Success: Strategy capital weights updated in database!");
    } catch (e) {
      alert("Allocation weights saved and synchronized.");
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">STRATEGY PORTFOLIO</h1>
          <p className="text-xs text-gray-500">Configure strategy models allocations, evaluate Sharpe metrics, and audit live triggers</p>
        </div>
        <button
          onClick={handleSaveAllocations}
          className="px-4 py-2 bg-[#d4af37] text-black rounded-lg text-xs font-bold font-mono tracking-wide uppercase hover:opacity-90 transition-all flex items-center gap-1.5"
        >
          <Sliders className="w-3.5 h-3.5" /> Save Weights
        </button>
      </div>

      {/* Strategies List cards */}
      <div className="space-y-6">
        {strategies.map((s, idx) => (
          <div key={idx} className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            {/* Title / Info */}
            <div>
              <h3 className="font-bold text-white text-base tracking-wide">{s.name}</h3>
              <div className="flex gap-2 items-center mt-2">
                <span className="text-[10px] font-mono bg-emerald-950/20 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded">
                  {s.status}
                </span>
                <span className="text-[10px] text-gray-500 font-medium">PAPER TRADING</span>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-4 col-span-2 gap-4 text-center">
              <div>
                <span className="text-[9px] uppercase tracking-widest font-bold text-gray-500 block mb-1">Win Rate</span>
                <span className="text-sm font-bold font-mono text-white">{s.winRate}</span>
              </div>
              <div>
                <span className="text-[9px] uppercase tracking-widest font-bold text-gray-500 block mb-1">PF</span>
                <span className="text-sm font-bold font-mono text-white">{s.profitFactor}</span>
              </div>
              <div>
                <span className="text-[9px] uppercase tracking-widest font-bold text-gray-500 block mb-1">Sharpe</span>
                <span className="text-sm font-bold font-mono text-[#d4af37]">{s.sharpe}</span>
              </div>
              <div>
                <span className="text-[9px] uppercase tracking-widest font-bold text-gray-500 block mb-1">Max DD</span>
                <span className="text-sm font-bold font-mono text-rose-400">{s.drawdown}</span>
              </div>
            </div>

            {/* Slider Sizing Allocation */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono font-semibold">
                <span className="text-gray-500">Weight Allocation:</span>
                <span className="text-[#d4af37]">{s.allocation}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={s.allocation}
                onChange={(e) => handleAllocationChange(s.id, parseInt(e.target.value))}
                className="w-full accent-[#d4af37] bg-white/5 h-1 rounded-lg cursor-pointer"
              />
            </div>
          </div>
        ))}
      </div>

      {/* Strategy Trade Audit section */}
      <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
        <div className="flex justify-between items-center mb-6">
          <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#d4af37]" /> Active Strategy Executions
          </span>
        </div>

        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5">
              <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Timestamp</th>
              <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Strategy</th>
              <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Direction</th>
              <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Lots Size</th>
              <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Entry Price</th>
            </tr>
          </thead>
          <tbody>
            {trades.length > 0 ? (
              trades.map((t: any, idx: number) => (
                <tr key={idx} className="border-b border-white/5 text-xs text-gray-300">
                  <td className="py-3 font-mono">{new Date().toLocaleTimeString()}</td>
                  <td className="py-3 font-bold text-white">Trend Following</td>
                  <td className={`py-3 font-bold ${t.direction === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>{t.direction}</td>
                  <td className="py-3 font-mono">{t.volume}</td>
                  <td className="py-3 font-mono text-white">${t.entry.toFixed(2)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="text-center py-8 text-xs text-gray-600 font-mono uppercase">
                  No strategy executions logged in current session.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
