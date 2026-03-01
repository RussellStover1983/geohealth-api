"use client";

import type { PlacesMeasures } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface HealthOutcomesGridProps {
  measures: PlacesMeasures;
}

interface MeasureConfig {
  key: keyof PlacesMeasures;
  label: string;
  /** National average for benchmarking */
  benchmark: number;
  max: number;
}

const MEASURES: MeasureConfig[] = [
  { key: "diabetes", label: "Diabetes", benchmark: 11.3, max: 25 },
  { key: "obesity", label: "Obesity", benchmark: 33.0, max: 50 },
  { key: "mhlth", label: "Mental Health", benchmark: 15.6, max: 25 },
  { key: "phlth", label: "Physical Health", benchmark: 12.2, max: 20 },
  { key: "bphigh", label: "High BP", benchmark: 32.4, max: 45 },
  { key: "casthma", label: "Asthma", benchmark: 9.6, max: 15 },
  { key: "chd", label: "Heart Disease", benchmark: 6.2, max: 12 },
  { key: "csmoking", label: "Smoking", benchmark: 16.1, max: 30 },
  { key: "access2", label: "No Insurance", benchmark: 11.0, max: 30 },
  { key: "checkup", label: "Checkup", benchmark: 74.2, max: 85 },
  { key: "dental", label: "Dental", benchmark: 62.7, max: 80 },
  { key: "sleep", label: "Short Sleep", benchmark: 35.6, max: 50 },
  { key: "lpa", label: "Inactivity", benchmark: 27.5, max: 45 },
  { key: "binge", label: "Binge Drinking", benchmark: 17.0, max: 25 },
];

function getSeverity(value: number, benchmark: number, key: string): "good" | "moderate" | "high" {
  // For checkup and dental, higher is better
  const higherIsBetter = key === "checkup" || key === "dental";
  const ratio = higherIsBetter ? benchmark / value : value / benchmark;
  if (ratio <= 0.85) return "good";
  if (ratio <= 1.15) return "moderate";
  return "high";
}

const severityStyles = {
  good: "bg-emerald-50 border-emerald-200 text-emerald-800",
  moderate: "bg-amber-50 border-amber-200 text-amber-800",
  high: "bg-red-50 border-red-200 text-red-800",
};

const severityDotStyles = {
  good: "bg-emerald-500",
  moderate: "bg-amber-500",
  high: "bg-red-500",
};

export function HealthOutcomesGrid({ measures }: HealthOutcomesGridProps) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {MEASURES.map(({ key, label, benchmark, max }) => {
        const value = measures[key];
        if (value == null) return null;

        const severity = getSeverity(value, benchmark, key as string);

        return (
          <div
            key={key}
            className={cn(
              "rounded-lg border p-2 transition-colors",
              severityStyles[severity]
            )}
          >
            <div className="flex items-center gap-1">
              <div className={cn("h-1.5 w-1.5 rounded-full", severityDotStyles[severity])} />
              <span className="text-[10px] font-medium leading-tight">{label}</span>
            </div>
            <p className="mt-0.5 text-lg font-bold tabular-nums leading-tight">
              {value.toFixed(1)}
              <span className="text-[10px] font-normal">%</span>
            </p>
          </div>
        );
      })}
    </div>
  );
}
