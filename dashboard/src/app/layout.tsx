import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aegis Gold — Institutional Trading Platform",
  description: "Institutional-grade agentic trading dashboard for XAU/USD.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#08080c] text-[#f3f4f6]">
        {children}
      </body>
    </html>
  );
}
