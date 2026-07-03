"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { 
  TrendingUp, TrendingDown, ShieldAlert, Cpu, 
  Wallet, Shield, Activity, RefreshCw, Clock,
  Percent, AlertTriangle, MessageSquareCode, Award
} from "lucide-react";

export default function OverviewPage() {
  const [data, setData] = useState<any>({
    live_price: 2330.45,
    equity: 100000.0,
    balance: 100000.0,
    drawdown: 0.0,
    positions: [],
    alerts: [],
    agents: [],
    regime: "NEUTRAL",
    volatility: 10.0,
    signal: "HOLD",
    confidence: 0.0,
    risk_score: 0.0,
    trend_strength: "WEAK",
    model_agreement: 100.0,
    feed_latency: 110.0,
    paper_pnl: 0.0,
    win_rate: 0.0,
    total_trades: 0,
    latest_reason: "No signals detected",
    llm_commentary: "Awaiting market stream synchronization...",
    status_flags: { stale: false, missing_ticks: false, abnormal_spike: false, api_delay: false }
  });

  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard");
    
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setData(payload);
        
        setHistory((prev) => {
          const updated = [...prev, { time: new Date().toLocaleTimeString(), equity: payload.equity }];
          if (updated.length > 50) updated.shift();
          return updated;
        });
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    return () => ws.close();
  }, []);

  // Determine signal styles
  const getSignalColor = (sig: string) => {
    if (sig === "BUY") return "text-emerald-400 border-emerald-500/30 bg-emerald-950/20";
    if (sig === "SELL") return "text-rose-400 border-rose-500/30 bg-rose-950/20";
    return "text-amber-400 border-amber-500/30 bg-amber-950/20";
  };

  const metrics = [
    { label: "AI Core Signal", val: data.signal || "HOLD", sub: `Confidence: ${data.confidence ?? 0}%`, icon: Cpu, color: getSignalColor(data.signal || "HOLD") },
    { label: "Paper Trade P&L", val: `$${(data.paper_pnl ?? 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`, sub: `Win Rate: ${data.win_rate ?? 0}% (${data.total_trades ?? 0} trades)`, icon: Award, color: (data.paper_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400" },
    { label: "Max Drawdown", val: `${((data.drawdown ?? 0) * 100).toFixed(2)}%`, sub: "Max Limit: 8.00%", icon: ShieldAlert, color: "text-amber-500" },
    { label: "Feed Latency", val: `${(data.feed_latency ?? 0).toFixed(1)} ms`, sub: data.status_flags?.stale ? "⚠️ FEEDS STALE" : "⚡ REAL-TIME", icon: Clock, color: (data.feed_latency ?? 0) > 250 ? "text-rose-400" : "text-emerald-400" }
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">QUANT LIVE INTELLIGENCE</h1>
          <p className="text-xs text-gray-500">Fast multi-model fusion & real-time risk validation</p>
        </div>
        
        {/* Status flags ribbon */}
        <div className="flex gap-3">
          {data.status_flags?.stale && (
            <span className="flex items-center gap-1 text-[10px] font-mono bg-rose-950/30 text-rose-400 border border-rose-500/20 px-2 py-1 rounded">
              <AlertTriangle className="w-3 h-3" /> FEED_STALE
            </span>
          )}
          {data.status_flags?.missing_ticks && (
            <span className="flex items-center gap-1 text-[10px] font-mono bg-rose-950/30 text-rose-400 border border-rose-500/20 px-2 py-1 rounded">
              <AlertTriangle className="w-3 h-3" /> MISSING_TICKS
            </span>
          )}
          {data.status_flags?.abnormal_spike && (
            <span className="flex items-center gap-1 text-[10px] font-mono bg-amber-950/30 text-amber-400 border border-amber-500/20 px-2 py-1 rounded">
              <AlertTriangle className="w-3 h-3" /> PRICE_SPIKE
            </span>
          )}
          <div className="flex items-center gap-2 text-xs font-mono text-gray-400 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] px-3 py-1.5 rounded-lg">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></div>
            Price: ${(data.live_price ?? 2330.45).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Primary Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {metrics.map((m, idx) => {
          const Icon = m.icon;
          return (
            <div key={idx} className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] flex justify-between items-start">
              <div>
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">{m.label}</span>
                <span className={`text-2xl font-bold tracking-tight font-mono ${m.color}`}>{m.val}</span>
                <span className="text-[10px] text-gray-400 block mt-2">{m.sub}</span>
              </div>
              <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                <Icon className={`w-5 h-5 ${m.color}`} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Intelligence & Strategy panels */}
      <div className="grid grid-cols-3 gap-6">
        {/* Model Consensus Metrics */}
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] flex flex-col justify-between">
          <div>
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono block mb-6">Model Telemetry Consensus</span>
            <div className="space-y-4">
              {[
                { name: "Model Agreement", val: `${data.model_agreement ?? 100}%`, valColor: "text-white" },
                { name: "Risk Score Meter", val: `${data.risk_score ?? 0}/100`, valColor: (data.risk_score ?? 0) > 60 ? "text-rose-400" : "text-emerald-400" },
                { name: "Trend Strength", val: data.trend_strength ?? "WEAK", valColor: "text-[#d4af37]" },
                { name: "Volatility Regime", val: (data.volatility ?? 0) > 40.0 ? "HIGH_VOL" : "LOW_VOL", valColor: "text-blue-400" }
              ].map((item, idx) => (
                <div key={idx} className="flex justify-between items-center text-xs p-3 rounded bg-white/2 border border-white/5">
                  <span className="text-gray-400">{item.name}</span>
                  <span className={`font-mono font-bold ${item.valColor}`}>{item.val}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="pt-4 border-t border-white/5 text-[10px] text-gray-500 font-mono">
            Reason: {data.latest_reason ?? "No active alerts"}
          </div>
        </div>

        {/* Real-time chart */}
        <div className="col-span-2 glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <div className="flex justify-between items-center mb-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono">Live Account Equity Curve</span>
            <span className="text-[10px] text-gray-500 font-mono">Total Net Assets: ${data.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
          </div>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history.length > 0 ? history : [{time: "Start", equity: 100000}]}>
                <defs>
                  <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#d4af37" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#d4af37" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis domain={["dataMin - 100", "dataMax + 100"]} hide />
                <Tooltip 
                  contentStyle={{ backgroundColor: "rgba(10,10,14,0.9)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}
                  labelStyle={{ color: "#d4af37", fontSize: "11px", fontWeight: "bold" }}
                  itemStyle={{ color: "#ffffff", fontSize: "12px" }}
                />
                <Area type="monotone" dataKey="equity" stroke="#d4af37" strokeWidth={2} fillOpacity={1} fill="url(#colorEquity)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Live AI commentary section */}
      <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] border-l-2 border-l-[#d4af37]">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquareCode className="w-5 h-5 text-[#d4af37]" />
          <span className="font-semibold text-sm tracking-wider uppercase text-white font-mono">Live AI Market commentary (LLM Layer)</span>
        </div>
        <div className="bg-black/30 border border-white/5 p-4 rounded-lg text-xs leading-relaxed text-gray-300 font-mono max-h-48 overflow-y-auto whitespace-pre-wrap">
          {data.llm_commentary}
        </div>
      </div>

      {/* Position and alert tables */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Exposure list */}
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <div className="flex justify-between items-center mb-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono">Active Paper Positions</span>
            <span className="text-[10px] text-gray-500">Live ticks sync</span>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Direction</th>
                  <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Entry Price</th>
                  <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Volume</th>
                  <th className="text-[10px] text-gray-500 uppercase tracking-widest py-2">Unrealized P&L</th>
                </tr>
              </thead>
              <tbody>
                {data.positions && data.positions.length > 0 ? (
                  data.positions.map((p: any, idx: number) => (
                    <tr key={idx} className="border-b border-white/5 text-sm">
                      <td className={`py-3 font-bold ${p.direction === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>{p.direction}</td>
                      <td className="py-3 font-mono text-white">${p.entry.toFixed(2)}</td>
                      <td className="py-3 text-white">{p.volume}</td>
                      <td className={`py-3 font-mono font-bold ${p.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ${p.pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="text-center py-8 text-xs text-gray-600 font-mono uppercase">
                      No active exposure. Platform is flat.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Alerts logs */}
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <div className="flex justify-between items-center mb-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono">System Audit Log</span>
            <span className="text-[10px] text-gray-500">Security triggers</span>
          </div>

          <div className="space-y-3 max-h-56 overflow-y-auto pr-2">
            {data.alerts && data.alerts.length > 0 ? (
              data.alerts.map((a: any, idx: number) => (
                <div key={idx} className={`p-3 rounded-lg border flex justify-between gap-4 text-xs ${
                  a.severity === 'CRITICAL' 
                    ? 'border-rose-500/20 bg-rose-950/10 text-rose-300' 
                    : a.severity === 'WARN'
                    ? 'border-amber-500/20 bg-amber-950/10 text-amber-300'
                    : 'border-white/5 bg-white/2 text-gray-300'
                }`}>
                  <div>{a.message}</div>
                  <div className="text-[10px] text-gray-500 whitespace-nowrap">{new Date(a.time).toLocaleTimeString()}</div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-xs text-gray-600 font-mono uppercase">
                Audit trail clear.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

