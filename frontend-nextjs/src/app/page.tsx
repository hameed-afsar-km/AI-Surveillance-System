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
  const [backendOnline, setBackendOnline] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    const [s, e] = await Promise.all([api.status(), api.events(30)]);
    if (s) {
      setStatus(s);
      setRunning(s.running);
      setBackendOnline(true);
    } else {
      setBackendOnline(false);
    }
    if (e) setEvents(e);
  }, []);

  useEffect(() => {
    poll();
    pollRef.current = setInterval(poll, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [poll]);

  const handleStart = async (mode: string, source: string) => {
    setError(null);
    const res = await api.start(mode, source);
    if (res?.error) setError(res.error);
    else if (res?.status === "started") setRunning(true);
    else setError("Backend offline.");
  };

  const handleStop = async () => {
    await api.stop();
    setRunning(false);
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
    <div className="min-h-screen bg-[#09090b] text-[#fafafa] selection:bg-blue-500/30 flex flex-col font-sans">
      <Navbar backendOnline={backendOnline} uptime={status?.uptime ?? 0} />

      <main className="flex-1 w-full max-w-[1720px] mx-auto p-4 md:p-6 lg:p-8 animate-fade-in flex flex-col xl:grid xl:grid-cols-[300px_minmax(0,1fr)_340px] gap-6">
        
        {/* Left Column: Controls & AI */}
        <div className="flex flex-col gap-6 h-full">
          <ControlPanel
            running={running}
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
             <VideoFeed running={running} />
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
