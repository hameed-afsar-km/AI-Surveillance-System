"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { VideoOff, Loader2 } from "lucide-react";

export default function VideoFeed({ running }: { running: boolean }) {
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

      {running && loading && !streamOk && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#18181b]">
          <Loader2 size={28} className="animate-spin text-[#3b82f6]" />
          <span className="text-sm font-medium text-[#a1a1aa] tracking-widest uppercase">Acquiring Feed</span>
        </div>
      )}

      {running && streamOk && (
        <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#09090b]/80 backdrop-blur-md border border-[#27272a] shadow-lg">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]"></span>
          <span className="text-[10px] font-bold tracking-widest uppercase text-[#fafafa]">Live View</span>
        </div>
      )}

      {!running && (
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
