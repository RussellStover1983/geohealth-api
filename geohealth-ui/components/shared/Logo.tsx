"use client";

import { Activity } from "lucide-react";

interface LogoProps {
  size?: "sm" | "md";
}

export function Logo({ size = "md" }: LogoProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-500">
        <Activity className="h-4 w-4 text-white" strokeWidth={2.5} />
      </div>
      {size === "md" && (
        <div className="flex flex-col">
          <span className="text-sm font-bold leading-tight tracking-tight text-stone-900">
            GeoHealth
          </span>
          <span className="text-[10px] font-medium leading-tight text-stone-400">
            SDOH Explorer
          </span>
        </div>
      )}
    </div>
  );
}
