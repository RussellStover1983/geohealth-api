"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { DemographicAverages } from "@/lib/api/types";

interface ComparisonBarsProps {
  averages: DemographicAverages[];
}

const METRIC_LABELS: Record<string, string> = {
  poverty_rate: "Poverty",
  uninsured_rate: "Uninsured",
  unemployment_rate: "Unemployment",
  median_household_income: "Income",
  median_age: "Median Age",
  total_population: "Population",
  sdoh_index: "SDOH Index",
};

export function ComparisonBars({ averages }: ComparisonBarsProps) {
  // Filter to rate metrics (not income/population) for cleaner display
  const rateMetrics = averages.filter(
    (a) =>
      a.metric !== "median_household_income" &&
      a.metric !== "total_population" &&
      a.metric !== "median_age"
  );

  const data = rateMetrics.map((avg) => ({
    name: METRIC_LABELS[avg.metric] || avg.metric,
    Tract: avg.tract_value,
    County: avg.county_avg,
    State: avg.state_avg,
    National: avg.national_avg,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 0, right: 12, left: 4, bottom: 0 }}
      >
        <XAxis type="number" tick={{ fontSize: 10, fill: "#A8A29E" }} axisLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 11, fill: "#57534E" }}
          axisLine={false}
          tickLine={false}
          width={90}
        />
        <Tooltip
          formatter={(value: number) => `${value?.toFixed(1)}%`}
          contentStyle={{
            backgroundColor: "#fff",
            border: "1px solid #E7E5E4",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend
          iconSize={8}
          wrapperStyle={{ fontSize: "11px", color: "#57534E" }}
        />
        <Bar dataKey="Tract" fill="#0D9488" radius={[0, 3, 3, 0]} barSize={8} />
        <Bar dataKey="County" fill="#99F6E4" radius={[0, 3, 3, 0]} barSize={8} />
        <Bar dataKey="State" fill="#3B82F6" radius={[0, 3, 3, 0]} barSize={8} opacity={0.7} />
        <Bar dataKey="National" fill="#A8A29E" radius={[0, 3, 3, 0]} barSize={8} opacity={0.5} />
      </BarChart>
    </ResponsiveContainer>
  );
}
