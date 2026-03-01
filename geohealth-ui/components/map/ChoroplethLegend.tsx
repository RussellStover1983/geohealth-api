"use client";

import type { MetricConfig } from "@/lib/map/styles";
import { getLegendItems } from "@/lib/map/styles";

interface ChoroplethLegendProps {
  metric: MetricConfig;
}

export function ChoroplethLegend({ metric }: ChoroplethLegendProps) {
  const items = getLegendItems(metric);

  return (
    <div className="rounded-xl border border-stone-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur-sm">
      <p className="mb-2 text-xs font-semibold text-stone-700">{metric.label}</p>
      <div className="flex flex-col gap-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className="h-3 w-6 rounded-sm"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[11px] tabular-nums text-stone-600">
              {item.label}
              {metric.unit && metric.unit !== "$" && metric.unit !== "0-1"
                ? ` ${metric.unit}`
                : ""}
            </span>
          </div>
        ))}
        <div className="flex items-center gap-2">
          <div
            className="h-3 w-6 rounded-sm"
            style={{ backgroundColor: "#D6D3D1" }}
          />
          <span className="text-[11px] text-stone-400">No data</span>
        </div>
      </div>
    </div>
  );
}
