"use client";

import { api, Event } from "@/lib/api";
import { ListFilter, Trash2 } from "lucide-react";

interface Props { events: Event[]; }

const TYPE_COLORS: Record<string, string> = {
  overcrowding:    "text-orange-400 bg-orange-400/10 border-orange-400/20",
  loitering:       "text-amber-400 bg-amber-400/10 border-amber-400/20",
  restricted_zone: "text-red-400 bg-red-400/10 border-red-400/20",
  sudden_crowd:    "text-purple-400 bg-purple-400/10 border-purple-400/20",
  custom:          "text-blue-400 bg-blue-400/10 border-blue-400/20",
};

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("en-GB", { hour12: false });
  } catch {
    return iso.slice(-8) || iso;
  }
}

function EventRow({ ev }: { ev: Event }) {
  const badgeClasses = TYPE_COLORS[ev.type] ?? "text-[#a1a1aa] bg-[#27272a]/50 border-[#3f3f46]";

  return (
    <div className="py-4 border-b border-[#27272a] last:border-0 hover:bg-[#18181b] px-6 transition-colors">
      <div className="flex items-center justify-between gap-3 mb-2">
        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${badgeClasses}`}>
          {ev.type.replace(/_/g, " ")}
        </span>
        <span className="text-[11px] font-mono text-[#71717a] font-medium tracking-tight">
          {fmtTime(ev.timestamp)}
        </span>
      </div>

      <p className="text-sm font-medium text-[#fafafa] leading-relaxed mb-3">
        {ev.message}
      </p>

      {ev.people_count > 0 && (
        <div className="flex items-center gap-2">
           <span className="text-[10px] uppercase font-semibold tracking-wider text-[#71717a]">Subjects:</span>
           <span className="text-xs font-mono font-bold text-[#fafafa] bg-[#27272a] px-2 py-0.5 rounded uppercase">{ev.people_count}</span>
        </div>
      )}
    </div>
  );
}

export default function EventLog({ events }: Props) {
  const sorted = [...events].reverse();

  const handleClear = async () => {
    if (confirm("Clear all recorded events?")) {
      await api.clearEvents();
    }
  };

  return (
    <div className="clean-panel flex flex-col h-full overflow-hidden bg-[#09090b]">
      <div className="flex items-center justify-between px-6 py-5 border-b border-[#27272a] bg-[#18181b]">
        <h3 className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-[#fafafa]">
          <ListFilter size={14} className="text-[#a1a1aa]" />
          Event Registry
        </h3>
        <div className="flex items-center gap-2">
          {events.length > 0 && (
            <>
              <div className="flex items-center justify-center px-2 py-0.5 rounded bg-[#27272a] border border-[#3f3f46]">
                <span className="text-xs font-bold text-[#fafafa]">{events.length}</span>
              </div>
              <button
                onClick={handleClear}
                className="p-1.5 rounded-md hover:bg-[#450a0a] text-[#71717a] hover:text-[#fca5a5] transition-colors bg-[#09090b] border border-[#27272a]"
                title="Clear Registry"
              >
                <Trash2 size={12} />
              </button>
            </>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto" style={{ maxHeight: "calc(100vh - 120px)" }}>
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <ListFilter size={24} className="text-[#3f3f46]" />
            <p className="text-sm font-medium text-[#71717a]">Registry Empty</p>
          </div>
        ) : (
          <div className="pb-4">
            {sorted.map((ev, i) => <EventRow key={`${ev.timestamp}-${i}`} ev={ev} />)}
          </div>
        )}
      </div>
    </div>
  );
}
