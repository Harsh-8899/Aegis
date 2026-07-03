"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, ShieldAlert, KeyRound, User, UserCheck } from "lucide-react";

import { API_URL } from "@/utils/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Quick Role pre-fills for evaluation convenience
  const roles = [
    { name: "Administrator", user: "admin", pass: "admin_password", color: "border-red-500/30 text-red-400 bg-red-950/10" },
    { name: "Trader Operator", user: "trader", pass: "trader_password", color: "border-emerald-500/30 text-emerald-400 bg-emerald-950/10" },
    { name: "Quant Researcher", user: "researcher", pass: "researcher_password", color: "border-blue-500/30 text-blue-400 bg-blue-950/10" },
    { name: "Viewer (Read Only)", user: "viewer", pass: "viewer_password", color: "border-gray-500/30 text-gray-400 bg-gray-950/10" },
  ];

  const handleQuickSelect = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError("");
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          username: username,
          password: password,
        }),
      });

      if (!response.ok) {
        const errDetail = await response.json();
        throw new Error(errDetail.detail || "Authentication Failed.");
      }

      const data = await response.json();
      
      // Save metadata
      localStorage.setItem("token", data.access_token);
      
      // Determine role based on username mapping
      const mappedRole = username === "admin" ? "admin" : username === "trader" ? "trader" : username === "researcher" ? "researcher" : "viewer";
      localStorage.setItem("user", JSON.stringify({ username, role: mappedRole }));

      router.push("/");
    } catch (err: any) {
      setError(err.message || "Connection refused by FastAPI API. Is backend server running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#050508] p-6">
      <div className="w-full max-w-md glass-panel p-8 bg-[rgba(10,10,14,0.85)] relative overflow-hidden">
        
        {/* Glow border element */}
        <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-[#d4af37] to-transparent"></div>

        {/* Logo and Intro */}
        <div className="flex flex-col items-center gap-2 mb-8 text-center">
          <div className="w-12 h-12 rounded-full bg-[rgba(212,175,55,0.1)] border border-[#d4af37]/30 flex items-center justify-center mb-2">
            <Shield className="w-6 h-6 text-[#d4af37]" />
          </div>
          <h1 className="text-xl font-bold tracking-widest text-white uppercase font-mono">AEGIS QUANT TERMINAL</h1>
          <p className="text-xs text-gray-500 font-medium">Secured XAU/USD Platform Access</p>
        </div>

        {/* Action Error Alerts */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-950/20 border border-red-500/30 flex gap-3 text-xs text-red-400">
            <ShieldAlert className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form Inputs */}
        <form onSubmit={handleLogin} className="space-y-5">
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-[#d4af37]" /> Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter account ID"
              className="w-full bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] px-4 py-3 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#d4af37] transition-all"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5 text-[#d4af37]" /> Passphrase
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] px-4 py-3 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#d4af37] transition-all"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 mt-2 rounded-lg bg-gradient-to-r from-[#f3e5ab] via-[#d4af37] to-[#aa7c11] text-black font-bold text-sm tracking-wider uppercase hover:opacity-90 active:scale-[0.99] transition-all disabled:opacity-50"
          >
            {loading ? "Decrypting credentials..." : "Authorize Terminal"}
          </button>
        </form>

        {/* Quick evaluation selectors */}
        <div className="mt-8 pt-6 border-t border-[rgba(255,255,255,0.08)]">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500 block mb-3 text-center">
            Quick-Select Testing Role accounts
          </span>
          <div className="grid grid-cols-2 gap-2.5">
            {roles.map((r) => (
              <button
                key={r.user}
                onClick={() => handleQuickSelect(r.user, r.pass)}
                className={`p-2.5 rounded-lg border text-left transition-all hover:brightness-110 flex flex-col gap-1 ${r.color}`}
              >
                <span className="text-[10px] font-bold truncate">{r.name}</span>
                <span className="text-[9px] font-mono opacity-60">ID: {r.user}</span>
              </button>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
