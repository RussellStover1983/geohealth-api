"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Layers, Stethoscope, BookOpen } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useGeoHealthStore } from "@/lib/store";
import { METRIC_CATEGORIES } from "@/lib/map/styles";
import { cn } from "@/lib/utils";

const PROVIDER_FILTERS = [
  { key: "all", label: "All Providers" },
  { key: "pcp", label: "PCPs" },
  { key: "fqhc", label: "FQHCs" },
  { key: "urgent_care", label: "Urgent Care" },
  { key: "rural_health_clinic", label: "Rural Health" },
] as const;

export function LayerPanel() {
  const { activeLayer, setActiveLayer, showProviders, setShowProviders, providerFilter, setProviderFilter } = useGeoHealthStore();
  const [openCategories, setOpenCategories] = useState<Record<string, boolean>>({
    "DPC Market Fit": true,
    Composite: true,
    Demographics: true,
    "Social Vulnerability (SVI)": false,
    "Health Outcomes (CDC PLACES)": false,
    "Environmental (EPA)": false,
  });

  const toggleCategory = (name: string) => {
    setOpenCategories((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 px-5 py-3">
        <Layers className="h-4 w-4 text-accent-600" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500">
          Map Layers
        </h2>
      </div>

      <div className="flex-1 space-y-0.5 px-2">
        {/* NPI Provider toggle */}
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-3 mb-2">
          <label className="flex cursor-pointer items-center gap-2.5">
            <input
              type="checkbox"
              checked={showProviders}
              onChange={(e) => setShowProviders(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-stone-300 text-accent-600 focus:ring-accent-500"
            />
            <Stethoscope className="h-3.5 w-3.5 text-accent-600" />
            <span className="text-xs font-medium text-stone-700">
              Show NPI Providers
            </span>
          </label>
          {showProviders && (
            <div className="mt-2 flex flex-wrap gap-1 ml-6">
              {PROVIDER_FILTERS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setProviderFilter(f.key)}
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-colors",
                    providerFilter === f.key
                      ? "bg-accent-100 text-accent-700"
                      : "bg-stone-100 text-stone-500 hover:bg-stone-200"
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
          {showProviders && (
            <p className="mt-1.5 ml-6 text-[10px] text-stone-400">
              Zoom into a city/metro area to see pins. Use +/- or scroll to zoom.
            </p>
          )}
        </div>

        {METRIC_CATEGORIES.map((category) => {
          const isOpen = openCategories[category.name] ?? false;
          const hasActive = category.metrics.some((m) => m.key === activeLayer);

          return (
            <Collapsible
              key={category.name}
              open={isOpen}
              onOpenChange={() => toggleCategory(category.name)}
            >
              <CollapsibleTrigger className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-stone-100">
                {isOpen ? (
                  <ChevronDown className="h-3.5 w-3.5 text-stone-400" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 text-stone-400" />
                )}
                <span
                  className={cn(
                    "flex-1 text-xs font-medium",
                    hasActive ? "text-accent-700" : "text-stone-700"
                  )}
                >
                  {category.name}
                </span>
                {hasActive && (
                  <div className="h-1.5 w-1.5 rounded-full bg-accent-500" />
                )}
              </CollapsibleTrigger>

              <CollapsibleContent>
                <p className="ml-9 mb-1 text-[10px] leading-snug text-stone-400">
                  {category.description}
                </p>
                <div className="ml-5 space-y-0.5 pb-1">
                  {category.metrics.map((metric) => {
                    const isActive = activeLayer === metric.key;
                    return (
                      <button
                        key={metric.key}
                        onClick={() => setActiveLayer(metric.key)}
                        className={cn(
                          "flex w-full items-center gap-2.5 rounded-md px-3 py-1.5 text-left text-xs transition-colors",
                          isActive
                            ? "bg-accent-50 font-medium text-accent-700"
                            : "text-stone-600 hover:bg-stone-50 hover:text-stone-800"
                        )}
                        aria-pressed={isActive}
                      >
                        <div
                          className={cn(
                            "h-2.5 w-2.5 rounded-full border-2 transition-colors",
                            isActive
                              ? "border-accent-500 bg-accent-500"
                              : "border-stone-300 bg-transparent"
                          )}
                        />
                        <span className="leading-tight">{metric.label}</span>
                      </button>
                    );
                  })}
                </div>
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>

      {/* Methodology link */}
      <div className="border-t border-stone-200 px-5 py-2">
        <Link
          href="/methodology"
          className="flex items-center gap-1.5 text-[10px] text-stone-400 hover:text-teal-600 transition-colors"
        >
          <BookOpen className="h-3 w-3" />
          Data sources &amp; methodology
        </Link>
      </div>
    </div>
  );
}
