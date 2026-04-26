"use client";

import { useState } from "react";
import { api, Event } from "@/lib/api";
import { ListFilter, Trash2, MapPin, Maximize2, X, Clock } from "lucide-react";

interface Props { events: Event[]; }

const TYPE_COLORS: Record<string, string> = {
  overcrowding:    "text-orange-400 bg-orange-400/10 border-orange-400/20",
  loitering:       "text-amber-400 bg-amber-400/10 border-amber-400/20",
  restricted_zone: "text-red-400 bg-red-400/10 border-red-400/20",
  sudden_crowd:    "text-purple-400 bg-purple-400/10 border-purple-400/20",
  custom:          "text-blue-400 bg-blue-400/10 border-blue-400/20",
  collision:       "text-red-500 bg-red-500/10 border-red-500/20",
  fire_hazard:     "text-orange-500 bg-orange-500/10 border-orange-500/20",
  medical_emergency: "text-pink-500 bg-pink-500/10 border-pink-500/20",
  theft:           "text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
};

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("en-GB", { hour12: false });
  } catch {
    return iso.slice(-8) || iso;
  }
}

function EventRow({ ev, compact = false }: { ev: Event, compact?: boolean }) {
  const badgeClasses = TYPE_COLORS[ev.type] ?? "text-[#a1a1aa] bg-[#27272a]/50 border-[#3f3f46]";

  return (
    <div className={`border-b border-[#27272a] last:border-0 hover:bg-[#18181b] transition-colors ${compact ? 'py-3 px-4' : 'py-4 px-6'}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${badgeClasses}`}>
          {ev.type.replace(/_/g, " ")}
        </span>
        <span className="text-[11px] font-mono text-[#71717a] font-medium tracking-tight flex items-center gap-1">
          <Clock size={10} /> {fmtTime(ev.timestamp)}
        </span>
      </div>

      <p className={`${compact ? 'text-xs' : 'text-sm'} font-medium text-[#fafafa] leading-relaxed mb-3`}>
        {ev.message}
      </p>

      <div className="flex flex-wrap items-center gap-4">
        {ev.location && (
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-semibold tracking-wider text-[#a1a1aa]">
            <MapPin size={12} className="text-[#3b82f6]" />
            {ev.location}
          </div>
        )}
        {ev.people_count > 0 && (
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-semibold tracking-wider text-[#71717a]">
             <span>Subjects:</span>
             <span className="font-mono font-bold text-[#fafafa] bg-[#27272a] px-1.5 py-0.5 rounded">{ev.people_count}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function EventLog({ events }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const sorted = [...events].reverse();

  const handleClear = async () => {
    if (confirm("Clear all recorded events?")) {
      await api.clearEvents();
    }
  };

  return (
    <>
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
                  onClick={() => setModalOpen(true)}
                  className="p-1.5 rounded-md text-[#71717a] hover:text-[#fafafa] hover:bg-[#27272a] transition-colors bg-[#09090b] border border-[#27272a]"
                  title="Expand History"
                >
                  <Maximize2 size={12} />
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

      {modalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#09090b] border border-[#27272a] w-full max-w-4xl max-h-full rounded-2xl flex flex-col overflow-hidden shadow-2xl">
            <div className="flex flex-wrap gap-4 items-center justify-between px-6 py-4 border-b border-[#27272a] bg-[#18181b]">
              <div className="flex items-center gap-3">
                <ListFilter size={20} className="text-blue-500" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Full Event History</h2>
                <span className="text-[10px] bg-[#27272a] px-2 py-1 rounded text-gray-300 font-mono">{events.length} records</span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleClear}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-[#450a0a] text-[#71717a] hover:text-[#fca5a5] transition-colors bg-[#09090b] border border-[#27272a] text-xs font-bold uppercase tracking-wider"
                >
                  <Trash2 size={14} /> Clear Log
                </button>
                <button
                  onClick={() => setModalOpen(false)}
                  className="p-1.5 rounded-md text-[#71717a] hover:text-white hover:bg-[#27272a] transition-colors bg-[#09090b] border border-[#27272a]"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-2">
              {sorted.map((ev, i) => (
                <div key={`modal-${ev.timestamp}-${i}`} className="bg-[#18181b] mx-2 my-2 rounded-lg border border-[#27272a]">
                  <EventRow ev={ev} compact={false} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
