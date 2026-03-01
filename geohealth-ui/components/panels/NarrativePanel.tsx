"use client";

import { Sparkles } from "lucide-react";

interface NarrativePanelProps {
  narrative: string;
}

export function NarrativePanel({ narrative }: NarrativePanelProps) {
  // Split into lead sentence and rest
  const firstPeriod = narrative.indexOf(". ");
  const leadSentence = firstPeriod > 0 ? narrative.slice(0, firstPeriod + 1) : narrative;
  const rest = firstPeriod > 0 ? narrative.slice(firstPeriod + 2) : "";

  return (
    <div className="rounded-xl border border-accent-200 bg-accent-50/50 p-4">
      <div className="mb-2 flex items-center gap-1.5">
        <Sparkles className="h-3.5 w-3.5 text-accent-600" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-accent-600">
          AI Summary
        </span>
      </div>
      <p className="text-sm leading-relaxed text-stone-700">
        <span className="font-medium italic">{leadSentence}</span>
        {rest && <> {rest}</>}
      </p>
    </div>
  );
}
