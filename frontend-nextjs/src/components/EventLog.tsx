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

export default function EventLog({ events: initialEvents }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [fullHistory, setFullHistory] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);

  const displayEvents = modalOpen ? fullHistory : initialEvents;
  const sorted = [...displayEvents].reverse();

  const handleExpand = async () => {
    setModalOpen(true);
    setLoading(true);
    const all = await api.events(0); // 0 now means all records
    if (all) setFullHistory(all);
    setLoading(false);
  };

  const handleClear = async () => {
    if (confirm("Clear all recorded events?")) {
      await api.clearEvents();
      setFullHistory([]);
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
            {initialEvents.length > 0 && (
              <>
                <div className="flex items-center justify-center px-2 py-0.5 rounded bg-[#27272a] border border-[#3f3f46]">
                  <span className="text-xs font-bold text-[#fafafa]">{initialEvents.length}</span>
                </div>
                <button
                  onClick={handleExpand}
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
          {initialEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-3">
              <ListFilter size={24} className="text-[#3f3f46]" />
              <p className="text-sm font-medium text-[#71717a]">Registry Empty</p>
            </div>
          ) : (
            <div className="pb-4">
              {[...initialEvents].reverse().map((ev, i) => <EventRow key={`${ev.timestamp}-${i}`} ev={ev} />)}
            </div>
          )}
        </div>
      </div>

      {/* Expanded History Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-black/90 backdrop-blur-md animate-fade-in">
          <div className="bg-[#09090b] border border-[#27272a] w-full max-w-6xl h-[90vh] rounded-3xl flex flex-col overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-8 py-6 border-b border-[#27272a] bg-[#18181b]/50">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-500">
                  <ListFilter size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">Intelligence Archive</h2>
                  <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest mt-0.5">
                    {loading ? "Synchronizing Records..." : `${fullHistory.length} Total Records Found`}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                <button
                  onClick={handleClear}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-[11px] font-bold uppercase tracking-wider text-red-400 hover:bg-red-400/5 border border-transparent hover:border-red-400/20 transition-all"
                >
                  <Trash2 size={14} /> Wipe History
                </button>
                <div className="w-px h-8 bg-[#27272a]" />
                <button
                  onClick={() => setModalOpen(false)}
                  className="w-10 h-10 rounded-xl bg-[#27272a] hover:bg-[#3f3f46] text-[#fafafa] flex items-center justify-center transition-all"
                >
                  <X size={20} />
                </button>
              </div>
            </div>
            
            <div className="flex-1 flex overflow-hidden">
              {/* Sidebar: Event List */}
              <div className="w-96 border-r border-[#27272a] overflow-y-auto bg-[#09090b]">
                {loading ? (
                  <div className="p-12 flex flex-col items-center gap-4">
                    <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <span className="text-[10px] font-bold text-[#52525b] uppercase tracking-widest">Accessing Logs</span>
                  </div>
                ) : (
                  <div className="divide-y divide-[#27272a]">
                    {sorted.map((ev, i) => (
                      <div 
                        key={`modal-list-${ev.timestamp}-${i}`}
                        onClick={() => setSelectedEvent(ev)}
                        className={`cursor-pointer transition-all ${selectedEvent?.timestamp === ev.timestamp ? 'bg-blue-500/10 border-l-2 border-l-blue-500' : 'hover:bg-[#18181b]'}`}
                      >
                         <div className="p-5">
                            <div className="flex items-center justify-between mb-2">
                               <span className={`text-[8px] font-black uppercase tracking-[0.2em] px-1.5 py-0.5 rounded ${TYPE_COLORS[ev.type] || 'bg-gray-500/20 text-gray-400'}`}>
                                  {ev.type.replace(/_/g, ' ')}
                               </span>
                               <span className="text-[10px] font-mono text-[#52525b]">{fmtTime(ev.timestamp)}</span>
                            </div>
                            <p className="text-xs font-medium text-[#a1a1aa] line-clamp-2 leading-relaxed">
                               {ev.message}
                            </p>
                         </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Detail View */}
              <div className="flex-1 overflow-y-auto bg-[#09090b] relative">
                {selectedEvent ? (
                  <div className="p-10 animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="max-w-3xl mx-auto space-y-10">
                       <header>
                          <div className="flex items-center gap-3 mb-4">
                             <div className={`w-3 h-3 rounded-full ${selectedEvent.severity === 'critical' ? 'bg-red-500 animate-pulse' : 'bg-blue-500'}`} />
                             <span className="text-xs font-bold uppercase tracking-[0.3em] text-[#52525b]">Incident Report: {selectedEvent.id}</span>
                          </div>
                          <h1 className="text-4xl font-extrabold text-[#fafafa] tracking-tight leading-tight">
                             {selectedEvent.message}
                          </h1>
                       </header>

                       <div className="grid grid-cols-2 gap-8">
                          <DetailCard label="Chronology" value={new Date(selectedEvent.timestamp).toLocaleString()} icon={<Clock size={16}/>} />
                          <DetailCard label="Geospatial ID" value={selectedEvent.location || "Camera Viewport-01"} icon={<MapPin size={16}/>} />
                          <DetailCard label="Subject Mass" value={`${selectedEvent.people_count} Classified Organisms`} icon={<Maximize2 size={16}/>} />
                          <DetailCard label="Classification" value={selectedEvent.type.toUpperCase()} icon={<ListFilter size={16}/>} />
                       </div>

                       {selectedEvent.ai_insight && (
                          <div className="glass-panel p-8 space-y-4 rounded-3xl border border-[#27272a] bg-[#18181b]/30">
                             <div className="flex items-center gap-3 text-blue-400">
                                <span className="text-[10px] font-black uppercase tracking-[0.4em]">Neural Analysis Output</span>
                             </div>
                             <p className="text-xl font-medium text-[#fafafa] leading-relaxed italic">
                                "{selectedEvent.ai_insight}"
                             </p>
                          </div>
                       )}

                       <div className="pt-10 border-t border-[#27272a]">
                          <p className="text-[10px] font-medium text-[#52525b] uppercase tracking-widest leading-loose">
                             Disclaimer: This intelligence summary was generated by the NexusVision behavioral engine. All timestamp data is synced with the edge processing unit.
                          </p>
                       </div>
                    </div>
                  </div>
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center opacity-20 pointer-events-none">
                     <ListFilter size={120} className="text-[#27272a] mb-6" />
                     <p className="text-xl font-bold uppercase tracking-[0.5em] text-[#a1a1aa]">Select Event to Expand</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DetailCard({ label, value, icon }: { label: string, value: string, icon: React.ReactNode }) {
  return (
    <div className="space-y-2">
       <div className="flex items-center gap-2 text-[#52525b]">
          {icon}
          <span className="text-[9px] font-black uppercase tracking-widest">{label}</span>
       </div>
       <p className="text-lg font-bold text-[#fafafa]">{value}</p>
    </div>
  );
}
