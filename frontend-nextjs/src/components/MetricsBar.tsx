"use client";

import { Users, AlertTriangle, Clock, Activity } from "lucide-react";
import { Status } from "@/lib/api";

interface Props {
  status: Status | null;
}

function fmtUptime(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  highlightClass?: string;
  icon: React.ReactNode;
}

function MetricCard({ label, value, highlightClass = "text-[#fafafa]", icon }: MetricCardProps) {
  return (
    <div className="flex-1 clean-panel p-5 flex items-center justify-between group">
      <div>
        <p className="text-[11px] font-bold text-[#a1a1aa] uppercase tracking-wider mb-2">{label}</p>
        <p className={`text-2xl font-bold tracking-tight ${highlightClass}`}>
          {value}
        </p>
      </div>
      <div className="text-[#52525b] group-hover:text-[#a1a1aa] transition-colors">
        {icon}
      </div>
    </div>
  );
}

export default function MetricsBar({ status }: Props) {
  const sv = status?.severity ?? "none";
  let alertVal = "NONE";
  let alertCls = "text-emerald-500 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]";
  
  if (status?.running) {
    alertVal = sv.toUpperCase();
    if (sv === "critical") alertCls = "text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]";
    else if (sv === "high") alertCls = "text-orange-500 drop-shadow-[0_0_8px_rgba(249,115,22,0.5)]";
    else if (sv === "medium") alertCls = "text-amber-500 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]";
    else if (sv === "low") alertCls = "text-blue-500 drop-shadow-[0_0_8px_rgba(59,130,246,0.5)]";
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 w-full">
      <MetricCard
        label="Subjects"
        value={status?.people_count ?? 0}
        icon={<Users size={24} />}
      />
      <MetricCard
        label="Threat Level"
        value={alertVal}
        highlightClass={alertCls}
        icon={<AlertTriangle size={24} className={status?.alert ? "animate-pulse" : ""} />}
      />
      <MetricCard
        label="Uptime"
        value={status?.running ? fmtUptime(status.uptime) : "00:00:00"}
        icon={<Clock size={24} />}
      />
      <MetricCard
        label="Frames"
        value={status?.frame_count ?? 0}
        icon={<Activity size={24} />}
      />
    </div>
  );
}
