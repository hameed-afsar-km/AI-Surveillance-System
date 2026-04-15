"use client";

import { Sparkles } from "lucide-react";

interface Props { summary: string; }

export default function AISummary({ summary }: Props) {
  return (
    <div className="clean-panel px-6 py-5 bg-[#09090b] border-l-4 border-l-blue-500">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} className="text-blue-500" />
        <span className="text-[11px] font-bold uppercase tracking-wider text-[#fafafa]">
          AI Analysis Checkpoint
        </span>
      </div>
      <p className="text-sm font-medium text-[#a1a1aa] leading-relaxed">
        {summary}
      </p>
    </div>
  );
}
