"use client";

import {
  Target,
  Activity,
  Building2,
  Stethoscope,
  Swords,
  AlertCircle,
} from "lucide-react";
import { useMarketFit } from "@/lib/api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { DimensionScore, ScoreCategory } from "@/lib/api/types";

const CATEGORY_COLORS: Record<ScoreCategory, string> = {
  EXCELLENT: "bg-emerald-500",
  STRONG: "bg-blue-500",
  MODERATE: "bg-amber-500",
  WEAK: "bg-red-400",
};

const CATEGORY_TEXT: Record<ScoreCategory, string> = {
  EXCELLENT: "text-emerald-700",
  STRONG: "text-blue-700",
  MODERATE: "text-amber-700",
  WEAK: "text-red-600",
};

const CATEGORY_BG: Record<ScoreCategory, string> = {
  EXCELLENT: "bg-emerald-50 border-emerald-200",
  STRONG: "bg-blue-50 border-blue-200",
  MODERATE: "bg-amber-50 border-amber-200",
  WEAK: "bg-red-50 border-red-200",
};

const DIMENSION_META: Record<string, { icon: typeof Target; label: string }> = {
  demand: { icon: Activity, label: "Demand" },
  supply_gap: { icon: Stethoscope, label: "Supply Gap" },
  affordability: { icon: Building2, label: "Affordability" },
  employer: { icon: Building2, label: "Employer" },
  competition: { icon: Swords, label: "Competition" },
};

function ScoreGauge({ score, category }: { score: number; category: ScoreCategory }) {
  return (
    <div className="flex flex-col items-center">
      <div className="relative h-24 w-24">
        {/* Background ring */}
        <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
          <circle
            cx="18"
            cy="18"
            r="15.5"
            fill="none"
            stroke="#e7e5e4"
            strokeWidth="3"
          />
          <circle
            cx="18"
            cy="18"
            r="15.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeDasharray={`${score * 0.974} 100`}
            strokeLinecap="round"
            className={CATEGORY_TEXT[category]}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-2xl font-bold tabular-nums", CATEGORY_TEXT[category])}>
            {Math.round(score)}
          </span>
        </div>
      </div>
      <Badge
        className={cn(
          "mt-1.5 text-[10px] font-semibold border",
          CATEGORY_BG[category],
          CATEGORY_TEXT[category]
        )}
      >
        {category}
      </Badge>
    </div>
  );
}

function DimensionBar({ name, dim }: { name: string; dim: DimensionScore }) {
  const meta = DIMENSION_META[name] || { icon: Target, label: name };
  const Icon = meta.icon;
  const pct = Math.min(100, Math.max(0, dim.score));

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs text-stone-600">
          <Icon className="h-3 w-3" />
          {meta.label}
        </span>
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium tabular-nums text-stone-800">
            {dim.score.toFixed(1)}
          </span>
          {dim.data_completeness < 1 && (
            <span className="text-[9px] text-stone-400" title="Partial data">
              ({Math.round(dim.data_completeness * 100)}%)
            </span>
          )}
        </div>
      </div>
      <div className="relative h-2 w-full rounded-full bg-stone-100">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            CATEGORY_COLORS[dim.category]
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-[10px] leading-tight text-stone-400">{dim.summary}</p>
    </div>
  );
}

export function DpcMarketFitCard({ geoid }: { geoid: string }) {
  const { data, isLoading, error } = useMarketFit(geoid);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-4 w-4 text-accent-600" />
            DPC Market Fit
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-center">
            <Skeleton className="h-24 w-24 rounded-full" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-4 w-4 text-accent-600" />
            DPC Market Fit
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-xs text-stone-400">
            <AlertCircle className="h-3.5 w-3.5" />
            <span>{error}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const { composite_score, dimensions, location, data_vintage } = data;
  const dimOrder = ["demand", "supply_gap", "affordability", "employer", "competition"];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-4 w-4 text-accent-600" />
          DPC Market Fit
          {location.market_population && (
            <Badge variant="secondary" className="ml-auto text-[10px]">
              Pop {location.market_population.toLocaleString()}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Composite Score Gauge */}
        <div className="flex justify-center">
          <ScoreGauge
            score={composite_score.value}
            category={composite_score.category}
          />
        </div>

        {/* Dimension Breakdowns */}
        <div className="space-y-3">
          {dimOrder.map((name) => {
            const dim = dimensions[name];
            if (!dim) return null;
            return <DimensionBar key={name} name={name} dim={dim} />;
          })}
        </div>

        {/* Data Sources */}
        <div className="flex flex-wrap gap-1 pt-1">
          {data_vintage.census_acs && (
            <Badge variant="secondary" className="text-[9px]">
              ACS {data_vintage.census_acs}
            </Badge>
          )}
          {data_vintage.npi && (
            <Badge variant="secondary" className="text-[9px]">
              NPI {data_vintage.npi}
            </Badge>
          )}
          {data_vintage.cbp && (
            <Badge variant="secondary" className="text-[9px]">
              CBP {data_vintage.cbp}
            </Badge>
          )}
          {data_vintage.cdc_places && (
            <Badge variant="secondary" className="text-[9px]">
              PLACES {data_vintage.cdc_places}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
