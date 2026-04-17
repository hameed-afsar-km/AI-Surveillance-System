"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { api, Status, Event } from "@/lib/api";
import Navbar from "@/components/Navbar";
import VideoFeed from "@/components/VideoFeed";
import MetricsBar from "@/components/MetricsBar";
import AlertBanner from "@/components/AlertBanner";
import ControlPanel from "@/components/ControlPanel";
import EventLog from "@/components/EventLog";
import AISummary from "@/components/AISummary";

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [internetConnected, setInternetConnected] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    const [s, e] = await Promise.all([api.status(), api.events(30)]);
    if (s) {
      setStatus(s);
      const raw = s as any;
      setRunning(raw.running ?? false);
      setStarting(raw.starting ?? false);
      setInternetConnected(raw.internet_connected ?? false);
      setBackendOnline(true);
    } else {
      setBackendOnline(false);
      setInternetConnected(false);
    }
    if (e) setEvents(e);
  }, []);

  useEffect(() => {
    poll();
    pollRef.current = setInterval(poll, 200);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [poll]);

  const [showSplash, setShowSplash] = useState(true);
  const autoStarted = useRef(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowSplash(false), 5000);
    return () => clearTimeout(timer);
  }, []);

  // Auto-Start logic: Trigger 'Engage' automatically once AI is warm
  useEffect(() => {
    if (backendOnline && status?.loading_progress === 100 && !running && !starting && !autoStarted.current) {
      console.log("System Calibration Complete - Engaging default feed...");
      autoStarted.current = true;
      handleStart("webcam", "0");
    }
  }, [backendOnline, status?.loading_progress, running, starting]);

  // Hide splash only when running actually starts
  useEffect(() => {
     if (running && showSplash) {
        const timer = setTimeout(() => setShowSplash(false), 800);
        return () => clearTimeout(timer);
     }
  }, [running, showSplash]);

  const handleStart = async (mode: string, source: string) => {
    setError(null);
    setStarting(true); 
    const res = await api.start(mode, source);
    if (!res) {
      setStarting(false);
      setError("Failed to reach backend.");
    } else if (res.error) {
      setStarting(false);
      setError(res.error);
    }
  };

  const handleStop = async () => {
    await api.stop();
    setRunning(false);
    setStarting(false);
  };

  const handleSoundToggle = async (v: boolean) => {
    setSoundEnabled(v);
    await api.settings({ sound_enabled: v });
  };

  const handleAiToggle = async (v: boolean) => {
    setAiEnabled(v);
    await api.settings({ ai_enabled: v });
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa] selection:bg-blue-500/30 flex flex-col font-sans overflow-x-hidden">
      <AnimatePresence>
        {showSplash && <SplashScreen progress={status?.loading_progress ?? 0} />}
      </AnimatePresence>

      <Navbar backendOnline={backendOnline} uptime={status?.uptime ?? 0} internetConnected={internetConnected} />

      <main className="flex-1 w-full max-w-[1720px] mx-auto p-4 md:p-6 lg:p-8 animate-fade-in flex flex-col xl:grid xl:grid-cols-[300px_minmax(0,1fr)_340px] gap-6">

        {/* Left Column: Controls & AI */}
        <div className="flex flex-col gap-6 h-full">
          <ControlPanel
            running={running}
            starting={starting}
            soundEnabled={soundEnabled}
            aiEnabled={aiEnabled}
            onStart={handleStart}
            onStop={handleStop}
            onSoundToggle={handleSoundToggle}
            onAiToggle={handleAiToggle}
            error={error}
            backendOnline={backendOnline}
          />
          {status?.periodic_summary && aiEnabled && (
            <AISummary summary={status.periodic_summary} />
          )}
        </div>

        {/* Center Column: Primary Video & Metrics */}
        <div className="flex flex-col gap-6">
          <div className="flex-1 min-h-[460px]">
            <VideoFeed running={running} starting={starting} progress={status?.loading_progress ?? 0} />
          </div>
          <AlertBanner status={status} />
          <MetricsBar status={status} />
        </div>

        {/* Right Column: Registry */}
        <div className="flex flex-col h-[600px] xl:h-full">
          <EventLog events={events} />
        </div>

      </main>
    </div>
  );
}

import { motion, AnimatePresence } from "framer-motion";
import { Shield, Eye, Cpu, Network } from "lucide-react";

function SplashScreen({ progress }: { progress: number }) {
  return (
    <motion.div 
      exit={{ opacity: 0, scale: 1.05, filter: "blur(10px)", transition: { duration: 1, ease: "easeInOut" } }}
      className="fixed inset-0 z-[200] bg-[#09090b] flex flex-col items-center justify-center p-6"
    >
      <div className="relative">
        {/* Animated Background Rings */}
        {[1, 2, 3].map((i) => (
          <motion.div
            key={i}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1 + i * 0.5, opacity: [0, 0.2, 0] }}
            transition={{ duration: 3, repeat: Infinity, delay: i * 0.5 }}
            className="absolute inset-0 rounded-full border border-blue-500/30"
          />
        ))}

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="relative z-10 bg-[#18181b] border border-[#27272a] p-12 rounded-[2.5rem] shadow-2xl flex flex-col items-center gap-8"
        >
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center shadow-[0_0_30px_rgba(37,99,235,0.4)]">
              <Shield size={32} className="text-white" />
            </div>
            <div className="h-12 w-[2px] bg-[#27272a]" />
            <div className="text-left">
              <h1 className="text-4xl font-extrabold tracking-tighter text-white">NEXUS<span className="text-blue-500">VISION</span></h1>
              <p className="text-[10px] font-bold tracking-[0.3em] text-[#52525b] uppercase">AI Surveillance Suite</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-6 w-full max-w-sm">
             <SplashFeature icon={<Eye size={18}/>} label="Neural Edge" />
             <SplashFeature icon={<Cpu size={18}/>} label="GPU Accel" />
             <SplashFeature icon={<Network size={18}/>} label="Realtime" />
          </div>

          <div className="space-y-4 w-full">
            <div className="h-1 w-full bg-[#09090b] rounded-full overflow-hidden border border-[#27272a]">
               <motion.div 
                 initial={false}
                 animate={{ width: `${progress}%` }}
                 transition={{ duration: 0.5, ease: "linear" }}
                 className="h-full bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.6)]"
               />
            </div>
            <p className="text-center text-[11px] font-medium text-blue-400 tracking-widest uppercase animate-pulse">
              {progress < 100 ? "Loading Neural Weights..." : "Calibration Finalizing..."}
            </p>
          </div>
        </motion.div>
      </div>
      
      <motion.p 
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }}
        className="mt-12 text-[#52525b] text-xs max-w-xs text-center leading-relaxed italic"
      >
        Enterprise-grade behavioral analysis and multi-departmental emergency routing platform.
      </motion.p>
    </motion.div>
  );
}

function SplashFeature({ icon, label }: { icon: React.ReactNode, label: string }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="w-10 h-10 rounded-xl bg-[#09090b] border border-[#27272a] flex items-center justify-center text-[#a1a1aa]">
        {icon}
      </div>
      <span className="text-[9px] font-bold text-[#52525b] uppercase tracking-tighter">{label}</span>
    </div>
  );
}
