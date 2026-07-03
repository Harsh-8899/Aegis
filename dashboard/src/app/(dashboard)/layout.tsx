"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  if (!isAuthenticated) {
    // Show empty loader while validating authorization token
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#08080c] text-[#d4af37]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-[#d4af37] border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs uppercase tracking-widest font-mono">Authenticating Terminal...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#08080c]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto max-h-screen p-8">
        {children}
      </main>
    </div>
  );
}
