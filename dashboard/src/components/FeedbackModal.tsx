"use client";

import React, { useState } from "react";
import { X, Star, MessageSquare } from "lucide-react";
import { API_URL } from "@/utils/api";

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function FeedbackModal({ isOpen, onClose }: FeedbackModalProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState("GENERAL");
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    setSuccess(false);

    try {
      const response = await fetch(`${API_URL}/api/v1/system/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: name || null,
          email: email || null,
          category,
          rating,
          comment,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to submit feedback.");
      }

      setSuccess(true);
      setName("");
      setEmail("");
      setComment("");
      setRating(5);
      setCategory("GENERAL");
    } catch (e: any) {
      setErrorMsg(e.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-white/10 bg-[#0e0e15]/95 shadow-[0_0_50px_rgba(0,0,0,0.8)] glass-panel">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 p-5">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-[#d4af37]" />
            <h3 className="font-mono text-sm font-bold tracking-wider text-white uppercase">Submit Tester Feedback</h3>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-white/5 hover:text-white transition-all">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        {success ? (
          <div className="p-8 text-center space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ✓
            </div>
            <h4 className="text-white font-mono text-sm uppercase font-bold">Feedback Submitted</h4>
            <p className="text-xs text-gray-400 leading-relaxed">
              Thank you for helping us test and improve Aegis Gold! Your comments have been saved directly to our audit database.
            </p>
            <button
              onClick={() => {
                setSuccess(false);
                onClose();
              }}
              className="mt-4 px-6 py-2 rounded-lg bg-white/5 border border-white/10 text-xs font-mono uppercase font-bold text-white hover:bg-white/10 transition-all"
            >
              Close Window
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            {errorMsg && (
              <div className="p-3 text-xs rounded border border-rose-500/20 bg-rose-950/20 text-rose-400 font-mono">
                Error: {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 font-mono">Name / Username</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Tester"
                  className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-[#d4af37] font-mono"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 font-mono">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tester@domain.com"
                  className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-[#d4af37] font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 font-mono">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-lg bg-[#141420] border border-white/10 px-3 py-2 text-xs text-white focus:outline-none focus:border-[#d4af37] font-mono"
                >
                  <option value="GENERAL">General Opinion</option>
                  <option value="BUG">Bug / Performance Issue</option>
                  <option value="FEATURE">Feature Suggestion</option>
                  <option value="UIUX">UI/UX Improvements</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 font-mono">Rating</label>
                <div className="flex items-center gap-1.5 h-9">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setRating(star)}
                      className="p-1 hover:scale-110 transition-transform"
                    >
                      <Star
                        className={`w-5 h-5 ${
                          star <= rating ? "fill-[#d4af37] text-[#d4af37]" : "text-gray-600"
                        }`}
                      />
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 font-mono">Comments / Detailed Feedback</label>
              <textarea
                value={comment}
                required
                minLength={5}
                maxLength={1000}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Share your thoughts about model Consensus, latencies, strategies, or simulation speed..."
                rows={4}
                className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-[#d4af37] font-mono resize-none"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3 rounded-lg bg-[#d4af37] text-black font-extrabold text-xs tracking-wider uppercase hover:brightness-110 active:scale-[0.99] disabled:opacity-50 transition-all font-mono"
              >
                {submitting ? "SUBMITTING TELEMETRY..." : "SUBMIT FEEDBACK"}
              </button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
