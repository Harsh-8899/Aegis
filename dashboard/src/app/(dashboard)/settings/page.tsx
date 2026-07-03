"use client";

import { useEffect, useState } from "react";
import { Settings, ShieldCheck, KeyRound, Database, Bell } from "lucide-react";

export default function SettingsPage() {
  const [role, setRole] = useState("viewer");

  // Mock Form Values
  const [apiKey, setApiKey] = useState("dev_mock_api_key_102552");
  const [apiSecret, setApiSecret] = useState("••••••••••••••••");
  const [retrainSchedule, setRetrainSchedule] = useState("Daily at 21:00 UTC");
  const [emailAlerts, setEmailAlerts] = useState(true);

  useEffect(() => {
    const user = localStorage.getItem("user");
    if (user) {
      try {
        setRole(JSON.parse(user).role);
      } catch (e) {}
    }
  }, []);

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    if (role !== "admin") {
      alert("Permission Denied: Only Admin users can adjust configuration settings.");
      return;
    }
    alert("Success: Credentials, scheduler variables, and notification keys synchronized with DB!");
  };

  const isViewOnly = role !== "admin";

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex justify-between items-center border-b border-[rgba(255,255,255,0.08)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-wider font-mono text-white">SYSTEM SETTINGS</h1>
          <p className="text-xs text-gray-500">Configure connection API keys, manage retraining chron schedules, and audit permissions</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* API settings */}
        <div className="col-span-2 glass-panel p-6 bg-[rgba(16,16,24,0.4)]">
          <form onSubmit={handleSaveSettings} className="space-y-6">
            
            {/* Broker credentials */}
            <div className="space-y-4">
              <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2 border-b border-white/5 pb-2">
                <KeyRound className="w-4 h-4 text-[#d4af37]" /> Broker API Configuration
              </span>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Broker Client Key</label>
                  <input
                    type="text"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    disabled={isViewOnly}
                    className="w-full bg-black/40 border border-white/10 px-4 py-3 rounded-lg text-xs text-white focus:outline-none focus:border-[#d4af37] disabled:opacity-50"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Broker Private Secret</label>
                  <input
                    type="password"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    disabled={isViewOnly}
                    className="w-full bg-black/40 border border-white/10 px-4 py-3 rounded-lg text-xs text-white focus:outline-none focus:border-[#d4af37] disabled:opacity-50"
                  />
                </div>
              </div>
            </div>

            {/* Model Retrainer scheduler */}
            <div className="space-y-4 pt-4">
              <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2 border-b border-white/5 pb-2">
                <Database className="w-4 h-4 text-[#d4af37]" /> ML Retraining Schedule
              </span>
              
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Retraining Cron Frequency</label>
                <input
                  type="text"
                  value={retrainSchedule}
                  onChange={(e) => setRetrainSchedule(e.target.value)}
                  disabled={isViewOnly}
                  className="w-full bg-black/40 border border-white/10 px-4 py-3 rounded-lg text-xs text-white focus:outline-none focus:border-[#d4af37] disabled:opacity-50"
                />
              </div>
            </div>

            {/* Notification settings */}
            <div className="space-y-4 pt-4">
              <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2 border-b border-white/5 pb-2">
                <Bell className="w-4 h-4 text-[#d4af37]" /> Alerts Notification Channels
              </span>
              
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="emailAlerts"
                  checked={emailAlerts}
                  onChange={(e) => setEmailAlerts(e.target.checked)}
                  disabled={isViewOnly}
                  className="w-4 h-4 accent-[#d4af37] rounded cursor-pointer disabled:opacity-50"
                />
                <label htmlFor="emailAlerts" className="text-xs text-gray-300 font-semibold select-none cursor-pointer">
                  Send Critical Risk alerts to Operator Slack/Telegram Hook
                </label>
              </div>
            </div>

            {!isViewOnly && (
              <button
                type="submit"
                className="px-6 py-2.5 bg-[#d4af37] text-black rounded-lg text-xs font-bold font-mono tracking-wider uppercase hover:opacity-90 transition-all"
              >
                Apply Parameters
              </button>
            )}
          </form>
        </div>

        {/* User permissions overview info panel */}
        <div className="glass-panel p-6 bg-[rgba(16,16,24,0.4)] flex flex-col justify-between h-fit">
          <div className="space-y-6">
            <span className="font-semibold text-sm tracking-wider uppercase text-gray-400 font-mono flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#d4af37]" /> Role Authorization Audit
            </span>

            <div className="space-y-4 text-xs">
              <div className="p-3 bg-white/2 border border-white/5 rounded-lg flex justify-between">
                <span className="text-gray-500 font-semibold">Your Active Role:</span>
                <span className="text-[#d4af37] font-bold uppercase tracking-wider">{role}</span>
              </div>
              
              <div className="space-y-2 pt-2 text-gray-400 leading-relaxed text-[11px]">
                <p><strong>Admin</strong>: Complete write access to all configuration limits, switches, and override buttons.</p>
                <p><strong>Trader</strong>: Able to execute manual orders, cancel orders, and trigger the Emergency Stop.</p>
                <p><strong>Researcher</strong>: Able to run backtests, trigger ML retraining, and generate research reports.</p>
                <p><strong>Viewer</strong>: Strictly locked to read-only summaries. All state-changing features are disabled.</p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
