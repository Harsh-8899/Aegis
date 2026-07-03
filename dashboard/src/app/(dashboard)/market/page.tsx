"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";
import { Calendar, Flame, Gauge, Globe, MessageSquareQuote } from "lucide-react";

export default function MarketPage() {
  const [price, setPrice] = useState(2330.45);
  const [spread, setSpread] = useState(1.8);
  const [volume, setVolume] = useState(45220);
  const [candleData, setCandleData] = useState<any[]>([]);

  // Connect to live WebSocket feed
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard");
    
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.live_price) {
          const nextPrice = payload.live_price;
          setPrice(nextPrice);
          setCandleData((history) => {
            const updated = [...history, { time: new Date().toLocaleTimeString(), price: nextPrice }];
            if (updated.length > 50) updated.shift();
            return updated;
          });
        }
      } catch (e) {
        console.error("WS parse error in market terminal", e);
      }
    };

    // Minor visual ticks variations
    const tickTimer = setInterval(() => {
      setSpread(Number((1.2 + Math.random() * 0.8).toFixed(1)));
      setVolume((prev) => prev + Math.floor(Math.random() * 5));
    }, 2000);

    return () => {
      ws.close();
      clearInterval(tickTimer);
    };
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">LIVE MARKET TERMINAL</h1>
          <p className="text-xs text-gray-500">Real-time XAU/USD feed analysis and macroeconomic trackers</p>
        </div>
      </div>

      {/* Main stats ribbon */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">XAU/USD Bid Price</span>
          <span className="text-3xl font-extrabold font-mono text-[#d4af37] tracking-wider animate-pulse">${price.toFixed(2)}</span>
        </div>
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">Bid-Ask Spread</span>
          <span className="text-3xl font-extrabold font-mono text-white tracking-wider">{spread} pips</span>
        </div>
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">Session Tick Volume</span>
          <span className="text-3xl font-extrabold font-mono text-white tracking-wider">{volume.toLocaleString()}</span>
        </div>
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-2">Volatility (ATR 14)</span>
          <span className="text-3xl font-extrabold font-mono text-amber-500 tracking-wider">12.45 pips</span>
        </div>
      </div>

      {/* Chart and Session overlaps */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <div className="flex justify-between items-center mb-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono">Live Candle Tick Chart</span>
            <span className="text-[10px] text-gray-500">1s updates</span>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={candleData.length > 0 ? candleData : [{time: "Start", price: 2330.45}]}>
                <defs>
                  <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#d4af37" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#d4af37" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis domain={["dataMin - 1", "dataMax + 1"]} hide />
                <Tooltip
                  contentStyle={{ backgroundColor: "rgba(10,10,14,0.9)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}
                  labelStyle={{ color: "#d4af37", fontSize: "11px", fontWeight: "bold" }}
                />
                <Area type="monotone" dataKey="price" stroke="#d4af37" strokeWidth={1.5} fillOpacity={1} fill="url(#colorPrice)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] flex flex-col justify-between">
          <div>
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2 mb-6">
              <Globe className="w-4 h-4 text-[#d4af37]" /> Global Market Sessions
            </span>
            <div className="space-y-4">
              {[
                { name: "London Session (GMT)", hours: "08:00 - 16:30", status: "ACTIVE", color: "text-emerald-400" },
                { name: "New York Session (EST)", hours: "13:00 - 21:00", status: "ACTIVE", color: "text-emerald-400" },
                { name: "Tokyo Session (JST)", hours: "00:00 - 09:00", status: "CLOSED", color: "text-gray-500" }
              ].map((s, idx) => (
                <div key={idx} className="flex justify-between items-center text-xs p-3 rounded bg-white/2 border border-white/5">
                  <div>
                    <strong className="text-white block">{s.name}</strong>
                    <span className="text-[10px] text-gray-500">{s.hours}</span>
                  </div>
                  <span className={`font-mono font-bold ${s.color}`}>{s.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* news sentiment cards and calendar event feeds */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Economic calendar cards */}
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <div className="flex justify-between items-center mb-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#d4af37]" /> Key Macro Economic Events
            </span>
          </div>
          <div className="space-y-3">
            {[
              { time: "14:30 GMT", country: "USD", event: "Non-Farm Payrolls (NFP)", impact: "HIGH", forecast: "185K", actual: "206K" },
              { time: "16:00 GMT", country: "USD", event: "ISM Services PMI", impact: "HIGH", forecast: "51.0", actual: "48.8" }
            ].map((e, idx) => (
              <div key={idx} className="p-3 bg-white/2 border border-white/5 rounded-lg flex justify-between items-center text-xs">
                <div>
                  <span className="text-gray-500 font-mono block mb-1">{e.time} • {e.country}</span>
                  <strong className="text-white text-sm">{e.event}</strong>
                </div>
                <div className="text-right">
                  <span className="text-rose-400 font-bold block text-[10px] mb-1">{e.impact} IMPACT</span>
                  <span className="text-gray-400">Fore: {e.forecast} | Act: {e.actual}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sentiment cards */}
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <div className="flex justify-between items-center mb-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2">
              <MessageSquareQuote className="w-4 h-4 text-[#d4af37]" /> AI News Sentiment Index
            </span>
          </div>
          <div className="space-y-3">
            {[
              { source: "Bloomberg", title: "Gold rallies as soft ISM PMI fuels Fed rate cut speculation.", sentiment: 0.85, color: "text-emerald-400" },
              { source: "Reuters", title: "US Dollar slides against majors, gold hits new daily high.", sentiment: 0.72, color: "text-emerald-400" }
            ].map((n, idx) => (
              <div key={idx} className="p-3 bg-white/2 border border-white/5 rounded-lg text-xs">
                <div className="flex justify-between text-gray-500 font-semibold mb-1">
                  <span>{n.source}</span>
                  <span className={n.color}>+{n.sentiment} Sentiment</span>
                </div>
                <p className="text-white font-medium">{n.title}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
