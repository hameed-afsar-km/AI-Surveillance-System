"use client";

import { useState, useEffect } from "react";
import { Play, Square, Settings2, Shield, Radio, Volume2, Cpu } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface Props {
  running: boolean;
  soundEnabled: boolean;
  aiEnabled: boolean;
  backendOnline: boolean;
  error: string | null;
  onStart: (mode: string, source: string) => Promise<void>;
  onStop: () => Promise<void>;
  onSoundToggle: (v: boolean) => Promise<void>;
  onAiToggle: (v: boolean) => Promise<void>;
}

export default function ControlPanel({
  running, soundEnabled, aiEnabled, backendOnline,
  error, onStart, onStop, onSoundToggle, onAiToggle,
}: Props) {
  const [mode, setMode] = useState<"simulation" | "webcam">("simulation");
  const [videoFiles, setVideoFiles] = useState<string[]>([]);
  const [videoFile, setVideoFile] = useState("");
  const [camIdx, setCamIdx] = useState(0);

  useEffect(() => {
    const fetchVideos = async () => {
      const files = await api.getVideos();
      if (files && files.length > 0) {
        setVideoFiles(files);
        setVideoFile(files[0]);
      }
    };
    if (backendOnline) fetchVideos();
  }, [backendOnline]);

  const handleStart = () => onStart(mode === "simulation" ? "file" : "webcam", mode === "simulation" ? videoFile : String(camIdx));

  return (
    <div className="clean-panel p-6 flex flex-col gap-6 select-none">
      <div>
        <div className="flex items-center gap-2 mb-4">
           <Settings2 size={16} className="text-[#a1a1aa]" />
           <h2 className="text-sm font-semibold tracking-tight text-[#fafafa]">Operations Control</h2>
        </div>
        
        <div className="space-y-4">
          <div className="flex bg-[#09090b] p-1 rounded-lg border border-[#27272a] relative overflow-hidden">
             {/* Slider Background */}
             <motion.div 
               className="absolute top-1 bottom-1 bg-[#27272a] rounded-md border border-[#3f3f46] shadow-sm"
               initial={false}
               animate={{ 
                 left: mode === "simulation" ? "4px" : "50%", 
                 width: "calc(50% - 4px)" 
               }}
               transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
             />
             
            <button
              onClick={() => setMode("simulation")}
              className={cn(
                "flex-1 py-1.5 text-[13px] font-medium z-10 transition-colors",
                mode === "simulation" ? "text-[#fafafa]" : "text-[#a1a1aa] hover:text-[#d4d4d8]"
              )}
            >
              Simulation
            </button>
            <button
              onClick={() => setMode("webcam")}
              className={cn(
                "flex-1 py-1.5 text-[13px] font-medium z-10 transition-colors",
                mode === "webcam" ? "text-[#fafafa]" : "text-[#a1a1aa] hover:text-[#d4d4d8]"
              )}
            >
              Live Cam
            </button>
          </div>

          <motion.div 
            layout
            className="space-y-2"
          >
            <label className="block text-[11px] font-semibold text-[#a1a1aa] uppercase tracking-wider">
              {mode === "simulation" ? "Target Repository" : "Webcam Interface"}
            </label>
            <AnimatePresence mode="wait">
              {mode === "simulation" ? (
                <motion.select
                  key="sim-select"
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  value={videoFile}
                  onChange={(e) => setVideoFile(e.target.value)}
                  className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2.5 text-sm text-[#fafafa] focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all appearance-none cursor-pointer"
                >
                  {videoFiles.map((v) => <option key={v} value={v}>{v}</option>)}
                </motion.select>
              ) : (
                <motion.input
                  key="webcam-idx"
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  type="number" min={0} max={9}
                  value={camIdx}
                  onChange={(e) => setCamIdx(Number(e.target.value))}
                  className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2.5 text-sm text-[#fafafa] focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
                 />
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>

      <div className="flex gap-3">
        <motion.button
          whileHover={!running && backendOnline ? { scale: 1.02, y: -1 } : {}}
          whileTap={!running && backendOnline ? { scale: 0.98 } : {}}
          onClick={handleStart}
          disabled={running || !backendOnline}
          className={cn(
            "flex-1 py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm font-semibold transition-all relative overflow-hidden",
            running 
              ? "bg-[#18181b] text-[#52525b] cursor-default border border-[#27272a]" 
              : "bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.2)]"
          )}
        >
          {running && (
             <motion.div 
               className="absolute inset-0 bg-white/5"
               animate={{ opacity: [0.1, 0.3, 0.1] }}
               transition={{ duration: 2, repeat: Infinity }}
             />
          )}
          <Play size={16} fill={running ? "currentColor" : "white"} /> 
          {running ? "Engaged" : "Engage"}
        </motion.button>

        <motion.button
          whileHover={running ? { scale: 1.02, y: -1 } : {}}
          whileTap={running ? { scale: 0.98 } : {}}
          onClick={onStop}
          disabled={!running}
          className={cn(
             "flex-1 py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm font-semibold transition-all",
             running
               ? "bg-[#450a0a] hover:bg-[#7f1d1d] text-[#fca5a5] border border-[#7f1d1d] shadow-[0_0_20px_rgba(127,29,29,0.2)]"
               : "bg-[#18181b] text-[#52525b] border border-[#27272a] opacity-50 cursor-not-allowed"
          )}
        >
          <Square size={16} fill="currentColor" /> Terminate
        </motion.button>
      </div>

      {error && (
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-[#450a0a] text-[#fca5a5] px-3 py-2 rounded-lg border border-[#7f1d1d] text-[13px] flex items-center gap-2"
        >
          <Shield size={14} />
          {error}
        </motion.div>
      )}

      <div className="pt-2 border-t border-[#27272a]">
        <h3 className="text-[11px] font-bold tracking-widest text-[#52525b] uppercase mb-4 mt-2">Active Subroutines</h3>
        
        <div className="space-y-4">
          <SubroutineToggle 
             icon={<Volume2 size={16}/>}
             label="Acoustic Pulse"
             active={soundEnabled}
             onToggle={() => onSoundToggle(!soundEnabled)}
          />
          <SubroutineToggle 
             icon={<Cpu size={16}/>}
             label="Neural Insight"
             active={aiEnabled}
             onToggle={() => onAiToggle(!aiEnabled)}
          />
        </div>
      </div>
    </div>
  );
}

function SubroutineToggle({ icon, label, active, onToggle }: { icon: React.ReactNode, label: string, active: boolean, onToggle: () => void }) {
  return (
    <label className="flex items-center justify-between cursor-pointer group">
      <div className="flex items-center gap-3">
        <span className={cn("transition-colors", active ? "text-blue-400" : "text-[#52525b]")}>
          {icon}
        </span>
        <span className="text-[13px] font-medium text-[#fafafa]">{label}</span>
      </div>
      <div 
        onClick={onToggle}
        className={cn(
          "w-10 h-[22px] rounded-full transition-all p-1 relative",
          active ? 'bg-blue-600 shadow-[0_0_10px_rgba(37,99,235,0.3)]' : 'bg-[#18181b] border border-[#27272a]'
        )}
      >
        <motion.div 
          className="absolute top-1 w-3.5 h-3.5 bg-white rounded-full shadow-lg"
          animate={{ x: active ? 18 : 2 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </div>
    </label>
  );
}
