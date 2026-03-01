"use client";

import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendYearData } from "@/lib/api/types";

interface TrendSparklineProps {
  years: TrendYearData[];
  metric: keyof Omit<TrendYearData, "year">;
  label: string;
  unit?: string;
  color?: string;
  height?: number;
  showAxis?: boolean;
}

export function TrendSparkline({
  years,
  metric,
  label,
  unit = "",
  color = "#0D9488",
  height = 60,
  showAxis = false,
}: TrendSparklineProps) {
  const data = years
    .filter((y) => y[metric] != null)
    .map((y) => ({
      year: y.year,
      value: y[metric] as number,
    }));

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center text-xs text-stone-400" style={{ height }}>
        Insufficient trend data
      </div>
    );
  }

  const change = data[data.length - 1].value - data[0].value;
  const changeColor = change > 0 ? "#EF4444" : "#22C55E";
  const changeSign = change > 0 ? "+" : "";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs text-stone-600">{label}</span>
        <span
          className="text-xs font-medium tabular-nums"
          style={{ color: changeColor }}
        >
          {changeSign}
          {change.toFixed(1)}
          {unit}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          {showAxis && (
            <>
              <XAxis
                dataKey="year"
                tick={{ fontSize: 10, fill: "#A8A29E" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#A8A29E" }}
                axisLine={false}
                tickLine={false}
                width={35}
              />
            </>
          )}
          <Tooltip
            formatter={(value: number) => [
              `${value.toFixed(1)}${unit}`,
              label,
            ]}
            labelFormatter={(year: number) => `${year}`}
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #E7E5E4",
              borderRadius: "8px",
              fontSize: "12px",
              padding: "6px 10px",
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3, fill: color, stroke: "#fff", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
