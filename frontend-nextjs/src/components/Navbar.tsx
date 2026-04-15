"use client";

import { ScanEye, Activity } from "lucide-react";

function fmtUptime(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function Navbar({ backendOnline, uptime }: { backendOnline: boolean; uptime: number }) {
  return (
    <nav className="sticky top-0 z-50 w-full bg-[#09090b]/80 backdrop-blur-md border-b border-[#27272a] px-8 py-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-white text-black shadow-sm">
          <ScanEye size={18} />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-[#fafafa]">
            Nexus Vision
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500'}`}></span>
          <span className="text-sm font-medium text-[#a1a1aa]">
            {backendOnline ? "Connected" : "Disconnected"}
          </span>
        </div>

        {uptime > 0 && (
          <div className="flex items-center gap-2 text-sm font-mono text-[#fafafa] bg-[#18181b] px-3 py-1.5 rounded-md border border-[#27272a]">
            <Activity size={14} className="text-[#a1a1aa]" />
            {fmtUptime(uptime)}
          </div>
        )}
      </div>
    </nav>
  );
}
