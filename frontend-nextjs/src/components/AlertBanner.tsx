"use client";

import { ShieldAlert, ShieldCheck, Brain } from "lucide-react";
import { Status } from "@/lib/api";

interface Props { status: Status | null; }

const SEVERITY_STYLES: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  none:     { bg: "bg-emerald-950/30", border: "border-emerald-900/50", text: "text-emerald-500", icon: "emerald-500" },
  low:      { bg: "bg-blue-950/30", border: "border-blue-900/50", text: "text-blue-500", icon: "blue-500" },
  medium:   { bg: "bg-amber-950/30", border: "border-amber-900/50", text: "text-amber-500", icon: "amber-500" },
  high:     { bg: "bg-orange-950/30", border: "border-orange-900/50", text: "text-orange-500", icon: "orange-500" },
  critical: { bg: "bg-red-950/30", border: "border-red-900/50", text: "text-red-500", icon: "red-500" },
};

export default function AlertBanner({ status }: Props) {
  if (!status || !status.running) return null;

  const sv   = status.severity ?? "none";
  const st   = SEVERITY_STYLES[sv] ?? SEVERITY_STYLES.none;
  const msg  = status.message || "System nominal. No threats detected.";
  const insight = status.ai_insight;
  const isAlert = status.alert;

  return (
    <div className={`clean-panel border ${st.border} ${st.bg} overflow-hidden`}>
      <div className="px-6 py-5 flex items-center gap-4">
        <div className={`w-2 h-2 rounded-full bg-${st.icon} ${isAlert ? "animate-pulse shadow-[0_0_8px_currentColor]" : ""} ${st.text}`}></div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            {isAlert ? <ShieldAlert size={14} className={st.text} /> : <ShieldCheck size={14} className={st.text} />}
            <span className={`text-[11px] font-bold uppercase tracking-widest ${st.text}`}>
              {isAlert ? `Threat Detected — ${sv}` : "Vanguard Active — All Clear"}
            </span>
          </div>
          <p className={`text-sm font-medium text-[#fafafa] truncate pr-4`}>
            {msg}
          </p>
        </div>
        
        {status.source_name && (
          <div className={`shrink-0 px-3 py-1.5 rounded-md bg-[#09090b] border ${st.border} text-[10px] font-mono tracking-widest uppercase font-semibold ${st.text}`}>
            SRC: {status.source_name}
          </div>
        )}
      </div>

      {insight && (
        <div className="px-6 py-4 border-t bg-[#09090b]/40 flex items-start gap-4" style={{ borderColor: 'var(--border)' }}>
          <Brain size={16} className={`mt-0.5 ${st.text}`} />
          <div className="flex-1">
            <p className={`text-[10px] font-bold uppercase tracking-widest mb-1 ${st.text}`}>Origin Assessment</p>
            <p className={`text-sm font-medium text-[#a1a1aa] leading-relaxed`}>"{insight}"</p>
          </div>
        </div>
      )}
    </div>
  );
}
