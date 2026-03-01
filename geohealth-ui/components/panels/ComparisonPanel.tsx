"use client";

import { useDemographicComparison } from "@/lib/api/hooks";
import { ComparisonBars } from "@/components/charts/ComparisonBars";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { BarChart3 } from "lucide-react";

interface ComparisonPanelProps {
  geoid: string;
}

export function ComparisonPanel({ geoid }: ComparisonPanelProps) {
  const { data, isLoading, error } = useDemographicComparison(geoid);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-accent-600" />
            Demographic Comparison
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-[280px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-accent-600" />
            Demographic Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-stone-400">
            {error || "Unable to load comparison data"}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-accent-600" />
          Demographic Comparison
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Percentile rankings */}
        <div>
          <p className="mb-2 text-xs font-medium text-stone-500">Percentile Rankings</p>
          <div className="space-y-2">
            {data.rankings.map((ranking) => (
              <div key={ranking.metric} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs capitalize text-stone-600">
                    {ranking.metric.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="flex gap-1.5">
                  <PercentileBadge label="County" value={ranking.county_percentile} />
                  <PercentileBadge label="State" value={ranking.state_percentile} />
                  <PercentileBadge label="National" value={ranking.national_percentile} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bar chart comparison */}
        <div>
          <p className="mb-2 text-xs font-medium text-stone-500">Tract vs Averages</p>
          <ComparisonBars averages={data.averages} />
        </div>
      </CardContent>
    </Card>
  );
}

function PercentileBadge({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  if (value == null) return null;

  const variant =
    value >= 75 ? "danger" : value >= 50 ? "warning" : "success";

  return (
    <Badge variant={variant} className="text-[10px] font-normal">
      {label}: {value.toFixed(0)}th
    </Badge>
  );
}
