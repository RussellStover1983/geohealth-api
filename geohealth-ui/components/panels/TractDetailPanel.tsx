"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  MapPin,
  Users,
  DollarSign,
  Shield,
  Heart,
  Leaf,
  TrendingUp,
  BarChart3,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useGeoHealthStore } from "@/lib/store";
import { useTrends } from "@/lib/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { NarrativePanel } from "./NarrativePanel";
import { ComparisonPanel } from "./ComparisonPanel";
import { DpcMarketFitCard } from "./DpcMarketFitCard";
import { SviRadar } from "@/components/charts/SviRadar";
import { HealthOutcomesGrid } from "@/components/charts/HealthOutcomesGrid";
import { TrendSparkline } from "@/components/charts/TrendSparkline";
import { MetricBar } from "@/components/charts/MetricBar";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { TractDataModel } from "@/lib/api/types";
import { SourceAttribution } from "@/components/shared/SourceAttribution";

function SdohPill({ value }: { value: number | null }) {
  if (value == null) return null;
  const label = value.toFixed(2);
  const variant =
    value >= 0.6 ? "danger" : value >= 0.4 ? "warning" : "success";
  return (
    <Badge variant={variant} className="text-xs tabular-nums">
      SDOH {label}
    </Badge>
  );
}

function DemographicsCard({ tract }: { tract: TractDataModel }) {
  const metrics = [
    {
      icon: Users,
      label: "Population",
      value: tract.total_population?.toLocaleString() ?? "N/A",
    },
    {
      icon: DollarSign,
      label: "Median Income",
      value: formatCurrency(tract.median_household_income),
    },
    {
      icon: null,
      label: "Poverty Rate",
      value: formatPercent(tract.poverty_rate),
    },
    {
      icon: null,
      label: "Uninsured",
      value: formatPercent(tract.uninsured_rate),
    },
    {
      icon: null,
      label: "Unemployment",
      value: formatPercent(tract.unemployment_rate),
    },
    {
      icon: null,
      label: "Median Age",
      value: tract.median_age ? `${tract.median_age.toFixed(1)} yrs` : "N/A",
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-4 w-4 text-accent-600" />
          Demographics
          <span className="ml-auto">
            <SourceAttribution componentKey="demographics" />
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          {metrics.map((m) => (
            <div key={m.label}>
              <p className="text-[10px] font-medium uppercase tracking-wider text-stone-400">
                {m.label}
              </p>
              <p className="text-sm font-semibold tabular-nums text-stone-800">
                {m.value}
              </p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function EpaCard({ epa }: { epa: NonNullable<TractDataModel["epa_data"]> }) {
  const metrics = [
    { key: "pm25", label: "PM2.5", max: 15, unit: "ug/m3" },
    { key: "ozone", label: "Ozone", max: 55, unit: "ppb" },
    { key: "lead_paint_pct", label: "Lead Paint", max: 0.8, unit: "" },
    { key: "air_toxics_cancer_risk", label: "Cancer Risk", max: 60, unit: "/M" },
    { key: "traffic_proximity", label: "Traffic", max: 500, unit: "" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Leaf className="h-4 w-4 text-accent-600" />
          Environmental (EPA)
          <span className="ml-auto flex items-center gap-1.5">
            {epa._source && (
              <Badge variant="secondary" className="text-[10px]">
                {epa._source === "ejscreen_api" ? "EPA Data" : "Estimated"}
              </Badge>
            )}
            <SourceAttribution componentKey="environmental" />
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {metrics.map(({ key, label, max, unit }) => {
          const value = epa[key];
          if (typeof value !== "number") return null;
          return (
            <MetricBar
              key={key}
              label={label}
              value={value}
              max={max}
              unit={unit}
              highIsBad={true}
              decimals={key === "lead_paint_pct" ? 2 : 1}
            />
          );
        })}
      </CardContent>
    </Card>
  );
}

function TrendsCard({ geoid }: { geoid: string }) {
  const { data, isLoading, error } = useTrends(geoid);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-accent-600" />
            Trends (2018–2022)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data || data.years.length < 2) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-accent-600" />
            Trends
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-stone-400">
            {error || "No trend data available for this tract"}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-accent-600" />
          Trends (2018–2022)
          <span className="ml-auto">
            <SourceAttribution componentKey="trends" />
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <TrendSparkline
          years={data.years}
          metric="poverty_rate"
          label="Poverty Rate"
          unit="%"
          color="#EF4444"
        />
        <TrendSparkline
          years={data.years}
          metric="median_household_income"
          label="Median Income"
          unit=""
          color="#22C55E"
        />
        <TrendSparkline
          years={data.years}
          metric="uninsured_rate"
          label="Uninsured Rate"
          unit="%"
          color="#F59E0B"
        />
      </CardContent>
    </Card>
  );
}

export function TractDetailPanel() {
  const { selectedTract, selectedNarrative, isDetailPanelOpen, closeDetailPanel } =
    useGeoHealthStore();
  const [showComparison, setShowComparison] = useState(false);

  return (
    <AnimatePresence>
      {isDetailPanelOpen && selectedTract && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          className="absolute right-0 top-0 z-20 h-full w-[400px] border-l border-stone-200 bg-white shadow-xl"
        >
          <ScrollArea className="h-full">
            <div className="p-5">
              {/* Header */}
              <div className="mb-4 flex items-start justify-between">
                <div className="flex-1 pr-4">
                  <h2 className="text-base font-semibold leading-tight text-stone-900">
                    {selectedTract.name || `Census Tract ${selectedTract.tract_code}`}
                  </h2>
                  <div className="mt-1.5 flex items-center gap-2">
                    <Badge variant="secondary" className="text-[10px] font-mono">
                      {selectedTract.geoid}
                    </Badge>
                    <SdohPill value={selectedTract.sdoh_index} />
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={closeDetailPanel}
                  className="h-8 w-8 shrink-0"
                  aria-label="Close detail panel"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="space-y-4">
                {/* AI Narrative */}
                {selectedNarrative && (
                  <NarrativePanel narrative={selectedNarrative} />
                )}

                {/* DPC Market Fit Score */}
                <DpcMarketFitCard geoid={selectedTract.geoid} />

                {/* Demographics */}
                <DemographicsCard tract={selectedTract} />

                {/* SVI Radar */}
                {selectedTract.svi_themes && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-accent-600" />
                        Social Vulnerability Index
                        <span className="ml-auto">
                          <SourceAttribution componentKey="svi" />
                        </span>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <SviRadar themes={selectedTract.svi_themes} />
                    </CardContent>
                  </Card>
                )}

                {/* Health Outcomes */}
                {selectedTract.places_measures && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Heart className="h-4 w-4 text-accent-600" />
                        Health Outcomes
                        <span className="ml-auto">
                          <SourceAttribution componentKey="health_outcomes" />
                        </span>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <HealthOutcomesGrid measures={selectedTract.places_measures} />
                    </CardContent>
                  </Card>
                )}

                {/* Environmental */}
                {selectedTract.epa_data && (
                  <EpaCard epa={selectedTract.epa_data} />
                )}

                {/* Trends */}
                <TrendsCard geoid={selectedTract.geoid} />

                {/* Comparison toggle */}
                <Separator />
                <Button
                  variant="outline"
                  className="w-full justify-between"
                  onClick={() => setShowComparison(!showComparison)}
                >
                  <span className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" />
                    Compare to Averages
                  </span>
                  {showComparison ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>

                {showComparison && (
                  <ComparisonPanel geoid={selectedTract.geoid} />
                )}

                {/* Bottom padding for scroll */}
                <div className="h-4" />
              </div>
            </div>
          </ScrollArea>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
