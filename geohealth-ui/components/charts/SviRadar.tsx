"use client";

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { SviThemes } from "@/lib/api/types";

interface SviRadarProps {
  themes: SviThemes;
}

const SVI_LABELS: Record<string, string> = {
  rpl_theme1: "Socioeconomic",
  rpl_theme2: "Household",
  rpl_theme3: "Minority/Lang",
  rpl_theme4: "Housing/Trans",
  rpl_themes: "Overall",
};

export function SviRadar({ themes }: SviRadarProps) {
  const data = Object.entries(SVI_LABELS).map(([key, label]) => ({
    subject: label,
    value: (themes[key as keyof SviThemes] ?? 0) * 100,
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
        <PolarGrid stroke="#E7E5E4" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fontSize: 11, fill: "#57534E" }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={{ fontSize: 10, fill: "#A8A29E" }}
          tickCount={5}
        />
        <Radar
          name="SVI Percentile"
          dataKey="value"
          stroke="#0D9488"
          fill="#14B8A6"
          fillOpacity={0.25}
          strokeWidth={2}
        />
        <Tooltip
          formatter={(value: number) => [`${value.toFixed(0)}th percentile`, "SVI"]}
          contentStyle={{
            backgroundColor: "#fff",
            border: "1px solid #E7E5E4",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
