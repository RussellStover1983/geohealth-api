"use client";

import { cn } from "@/lib/utils";

interface MetricBarProps {
  label: string;
  value: number | null;
  max: number;
  unit?: string;
  benchmark?: number;
  benchmarkLabel?: string;
  highIsBad?: boolean;
  decimals?: number;
}

export function MetricBar({
  label,
  value,
  max,
  unit = "%",
  benchmark,
  benchmarkLabel,
  highIsBad = true,
  decimals = 1,
}: MetricBarProps) {
  if (value == null) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs text-stone-600">{label}</span>
          <span className="text-xs text-stone-400">N/A</span>
        </div>
        <div className="h-2 w-full rounded-full bg-stone-100" />
      </div>
    );
  }

  const percent = Math.min(100, Math.max(0, (value / max) * 100));
  const benchmarkPercent = benchmark != null ? Math.min(100, (benchmark / max) * 100) : null;

  // Color based on severity
  const getBarColor = () => {
    const ratio = value / max;
    if (!highIsBad) {
      if (ratio >= 0.6) return "bg-emerald-500";
      if (ratio >= 0.3) return "bg-amber-400";
      return "bg-red-400";
    }
    if (ratio <= 0.3) return "bg-emerald-500";
    if (ratio <= 0.6) return "bg-amber-400";
    return "bg-red-400";
  };

  const formatValue = () => {
    if (unit === "$") return `$${value.toLocaleString()}`;
    return `${value.toFixed(decimals)}${unit}`;
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-stone-600">{label}</span>
        <span className="text-xs font-medium tabular-nums text-stone-800">
          {formatValue()}
        </span>
      </div>
      <div className="relative h-2 w-full rounded-full bg-stone-100">
        <div
          className={cn("h-full rounded-full transition-all duration-500", getBarColor())}
          style={{ width: `${percent}%` }}
        />
        {benchmarkPercent != null && (
          <div
            className="absolute top-0 h-full w-0.5 bg-stone-800"
            style={{ left: `${benchmarkPercent}%` }}
            title={benchmarkLabel ? `${benchmarkLabel}: ${benchmark}` : undefined}
          />
        )}
      </div>
    </div>
  );
}
