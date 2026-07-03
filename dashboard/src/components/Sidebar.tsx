"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  LayoutDashboard, TrendingUp, Cpu, LineChart, 
  ShieldAlert, ArrowUpDown, FlaskConical, FileText, 
  Settings, LogOut, Shield, ShieldCheck, MessageSquare
} from "lucide-react";
import { useEffect, useState } from "react";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState({ username: "Viewer", role: "viewer" });
  const [isPaper, setIsPaper] = useState(true);

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {}
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  const navItems = [
    { label: "Overview", href: "/", icon: LayoutDashboard },
    { label: "Live Market", href: "/market", icon: TrendingUp },
    { label: "Agent Control", href: "/agents", icon: Cpu },
    { label: "Strategies", href: "/strategies", icon: LineChart },
    { label: "Risk Management", href: "/risk", icon: ShieldAlert },
    { label: "Trade Execution", href: "/execution", icon: ArrowUpDown },
    { label: "Research Lab", href: "/research", icon: FlaskConical },
    { label: "Logs & Audit", href: "/audit", icon: FileText },
    { label: "Settings", href: "/settings", icon: Settings },
  ];

  return (
    <aside className="w-64 border-r border-[rgba(255,255,255,0.08)] bg-[rgba(10,10,14,0.9)] flex flex-col h-screen sticky top-0">
      {/* Header Logo */}
      <div className="p-6 border-b border-[rgba(255,255,255,0.08)] flex items-center gap-3">
        <Shield className="w-8 h-8 text-[#d4af37] filter drop-shadow-[0_0_8px_rgba(212,175,55,0.3)]" />
        <div>
          <span className="font-semibold text-lg tracking-wider text-[#f3f4f6]">AEGIS GOLD</span>
          <p className="text-[10px] text-gray-500 font-medium">XAU/USD PLATFORM</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? "bg-[rgba(212,175,55,0.15)] text-[#d4af37] border-l-2 border-[#d4af37]"
                  : "text-gray-400 hover:text-white hover:bg-[rgba(255,255,255,0.03)]"
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </Link>
          );
        })}
        <button
          onClick={() => {
            if (typeof window !== "undefined") {
              window.dispatchEvent(new CustomEvent("open-feedback-modal"));
            }
          }}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-[rgba(255,255,255,0.03)] transition-all"
        >
          <MessageSquare className="w-4 h-4 text-[#d4af37]" />
          Submit Feedback
        </button>
      </nav>

      {/* Mode Selector Info */}
      <div className="p-4 mx-4 mb-4 rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs">
          <span className="text-gray-400">Trading Mode:</span>
          <span className={`font-semibold ${isPaper ? "text-[#d4af37]" : "text-red-500"}`}>
            {isPaper ? "PAPER TRADING" : "LIVE (LOCKED)"}
          </span>
        </div>
        <button
          onClick={() => {
            if (isPaper) {
              alert("Warning: Live execution requires compliance verification and active API keys. Live trading is currently locked in mock paper-trading mode for capital security.");
            } else {
              setIsPaper(true);
            }
          }}
          className={`w-full py-1.5 rounded-lg text-xs font-bold text-center border transition-all ${
            isPaper
              ? "border-[#d4af37] text-[#d4af37] hover:bg-[rgba(212,175,55,0.05)]"
              : "border-red-500 text-red-500 hover:bg-red-500/10"
          }`}
        >
          {isPaper ? "Request Live Unlock" : "Back to Paper Mode"}
        </button>
      </div>

      {/* User Info & Logout Footer */}
      <div className="p-6 border-t border-[rgba(255,255,255,0.08)] flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[rgba(212,175,55,0.1)] border border-[#d4af37]/20 flex items-center justify-center text-[#d4af37] font-semibold text-sm">
            {user.username[0].toUpperCase()}
          </div>
          <div>
            <div className="text-sm font-semibold text-white truncate max-w-[120px]">{user.username}</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-[#d4af37]" />
              {user.role}
            </div>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-xs font-medium text-red-400 hover:text-red-300 transition-colors w-fit"
        >
          <LogOut className="w-4 h-4" />
          Logout Terminal
        </button>
      </div>
    </aside>
  );
}
