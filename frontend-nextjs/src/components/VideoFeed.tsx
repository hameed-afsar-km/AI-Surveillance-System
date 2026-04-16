"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { VideoOff, Loader2, Cpu } from "lucide-react";

export default function VideoFeed({ running, starting, progress = 0 }: { running: boolean; starting?: boolean; progress?: number }) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [streamOk, setStreamOk] = useState(false);
  const [loading, setLoading] = useState(false);
  const streamActive = useRef(false);

  useEffect(() => {
    if (!running) {
      setStreamOk(false);
      setLoading(false);
      if (imgRef.current) imgRef.current.src = "";
      streamActive.current = false;
      return;
    }

    if (streamActive.current) return;
    streamActive.current = true;
    setLoading(true);

    const url = api.streamUrl();
    const img = imgRef.current;
    if (!img) return;

    img.src = `${url}?t=${Date.now()}`;
    const onLoad = () => { setStreamOk(true); setLoading(false); };
    const onError = () => { setStreamOk(false); setLoading(false); streamActive.current = false; };
    img.addEventListener("load", onLoad);
    img.addEventListener("error", onError);

    return () => {
      img.removeEventListener("load", onLoad);
      img.removeEventListener("error", onError);
      if (imgRef.current) imgRef.current.src = "";
      streamActive.current = false;
    };
  }, [running]);

  return (
    <div className="relative rounded-xl overflow-hidden clean-panel w-full max-h-[85vh] aspect-video flex items-center justify-center border border-[#27272a] bg-[#09090b]">
      <img
        ref={imgRef}
        alt="Live Subject Feed"
        className="max-w-full max-h-full object-contain mx-auto"
        style={{ display: running ? "block" : "none", opacity: streamOk ? 1 : 0 }}
      />

      {/* Initialising: YOLO/DeepSort loading in background */}
      {starting && !running && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 bg-[#18181b]">
          <div className="flex flex-col items-center gap-3">
            <Cpu size={32} className="text-blue-400 animate-pulse" />
            <span className="text-sm font-medium text-[#a1a1aa] tracking-widest uppercase">Initialising AI Engines</span>
          </div>
          
          <div className="w-64 space-y-2">
            <div className="h-1.5 w-full bg-[#09090b] rounded-full overflow-hidden border border-[#27272a]">
              <div 
                className="h-full bg-blue-500 transition-all duration-500 ease-out shadow-[0_0_10px_rgba(59,130,246,0.5)]" 
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between items-center text-[10px] font-mono uppercase tracking-tight">
              <span className="text-[#52525b]">{progress < 100 ? "Booting PyTorch..." : "Ready"}</span>
              <span className="text-blue-400">{progress}%</span>
            </div>
          </div>

          <span className="text-[11px] text-[#52525b] max-w-[200px] text-center italic">
            Allocating neural weights and warming up GPU/CPU kernels...
          </span>
        </div>
      )}

      {/* Running but stream not ready yet */}
      {running && loading && !streamOk && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#18181b]">
          <Loader2 size={28} className="animate-spin text-[#3b82f6]" />
          <span className="text-sm font-medium text-[#a1a1aa] tracking-widest uppercase">Acquiring Feed</span>
        </div>
      )}

      {/* Live badge */}
      {running && streamOk && (
        <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#09090b]/80 backdrop-blur-md border border-[#27272a] shadow-lg">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]"></span>
          <span className="text-[10px] font-bold tracking-widest uppercase text-[#fafafa]">Live View</span>
        </div>
      )}

      {/* Standby */}
      {!running && !starting && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#18181b]/50">
          <div className="w-14 h-14 rounded-full bg-[#09090b] border border-[#27272a] flex items-center justify-center shadow-inner">
            <VideoOff size={24} className="text-[#52525b]" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-[#fafafa]">System Standby</p>
            <p className="text-xs text-[#a1a1aa] mt-1">Sensor array is currently offline.</p>
          </div>
        </div>
      )}
    </div>
  );
}
