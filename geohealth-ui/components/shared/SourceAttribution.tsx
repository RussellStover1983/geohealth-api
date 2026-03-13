"use client";

import { Info } from "lucide-react";
import Link from "next/link";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { getSourcesForComponent } from "@/lib/data-sources";

interface SourceAttributionProps {
  /** Key matching COMPONENT_SOURCES in data-sources.ts */
  componentKey: string;
  className?: string;
}

/**
 * Compact inline data source citation. Shows source abbreviations with a
 * tooltip revealing full names and a link to the methodology page.
 */
export function SourceAttribution({ componentKey, className }: SourceAttributionProps) {
  const sources = getSourcesForComponent(componentKey);
  if (sources.length === 0) return null;

  const label = sources.map((s) => s.name).join(", ");

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={`inline-flex items-center gap-1 text-[10px] text-stone-400 hover:text-stone-600 cursor-help transition-colors ${className ?? ""}`}
        >
          <Info className="h-3 w-3 shrink-0" />
          <span className="truncate">{label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-xs">
        <div className="space-y-1.5">
          {sources.map((s) => (
            <div key={s.id}>
              <p className="font-medium">{s.fullName}</p>
              <p className="text-[10px] text-stone-300">
                {s.provider} &middot; {s.vintage}
              </p>
            </div>
          ))}
          <Link
            href="/methodology"
            className="mt-1 block text-[10px] text-teal-300 underline hover:text-teal-200"
          >
            View full methodology
          </Link>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
