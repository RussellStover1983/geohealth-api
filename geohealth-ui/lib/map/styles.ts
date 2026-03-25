/**
 * Choropleth color scales and metric configuration for map rendering.
 */

export interface MetricConfig {
  key: string;
  label: string;
  unit: string;
  /** Range for color interpolation [min, max] */
  range: [number, number];
  /** Whether higher values are negative (red scale) or positive (teal scale) */
  highIsBad: boolean;
  /** Number of decimal places for display */
  decimals: number;
}

// Sequential teal scale (high = good)
export const POSITIVE_COLORS = ["#F0FDFA", "#99F6E4", "#2DD4BF", "#0D9488", "#134E4A"];

// Sequential red scale (high = bad)
export const NEGATIVE_COLORS = ["#FEF2F2", "#FECACA", "#F87171", "#DC2626", "#7F1D1D"];

// All available SDOH metrics organized by category
export const METRIC_CATEGORIES: {
  name: string;
  description: string;
  metrics: MetricConfig[];
}[] = [
  {
    name: "DPC Market Fit",
    description: "Direct Primary Care viability estimate",
    metrics: [
      {
        key: "dpc_market_fit",
        label: "Overall Estimate",
        unit: "score",
        range: [30, 75],
        highIsBad: false,
        decimals: 0,
      },
      {
        key: "dpc_demand",
        label: "Demand",
        unit: "score",
        range: [0, 100],
        highIsBad: false,
        decimals: 0,
      },
      {
        key: "dpc_affordability",
        label: "Affordability",
        unit: "score",
        range: [0, 100],
        highIsBad: false,
        decimals: 0,
      },
    ],
  },
  {
    name: "Composite",
    description: "Overall vulnerability scores",
    metrics: [
      {
        key: "sdoh_index",
        label: "SDOH Index",
        unit: "0-1",
        range: [0, 1],
        highIsBad: true,
        decimals: 2,
      },
    ],
  },
  {
    name: "Demographics",
    description: "American Community Survey",
    metrics: [
      {
        key: "median_household_income",
        label: "Median Household Income",
        unit: "$",
        range: [20000, 120000],
        highIsBad: false,
        decimals: 0,
      },
      {
        key: "poverty_rate",
        label: "Poverty Rate",
        unit: "%",
        range: [0, 40],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "uninsured_rate",
        label: "Uninsured Rate",
        unit: "%",
        range: [0, 30],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "unemployment_rate",
        label: "Unemployment Rate",
        unit: "%",
        range: [0, 25],
        highIsBad: true,
        decimals: 1,
      },
    ],
  },
  {
    name: "Social Vulnerability (SVI)",
    description: "CDC/ATSDR Social Vulnerability Index",
    metrics: [
      {
        key: "svi_themes.rpl_themes",
        label: "Overall SVI",
        unit: "0-1",
        range: [0, 1],
        highIsBad: true,
        decimals: 2,
      },
      {
        key: "svi_themes.rpl_theme1",
        label: "Socioeconomic Status",
        unit: "0-1",
        range: [0, 1],
        highIsBad: true,
        decimals: 2,
      },
      {
        key: "svi_themes.rpl_theme2",
        label: "Household Characteristics",
        unit: "0-1",
        range: [0, 1],
        highIsBad: true,
        decimals: 2,
      },
      {
        key: "svi_themes.rpl_theme3",
        label: "Minority Status / Language",
        unit: "0-1",
        range: [0, 1],
        highIsBad: true,
        decimals: 2,
      },
      {
        key: "svi_themes.rpl_theme4",
        label: "Housing / Transportation",
        unit: "0-1",
        range: [0, 1],
        highIsBad: true,
        decimals: 2,
      },
    ],
  },
  {
    name: "Health Outcomes (CDC PLACES)",
    description: "Model-based health estimates",
    metrics: [
      {
        key: "places_measures.diabetes",
        label: "Diabetes",
        unit: "%",
        range: [5, 25],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.obesity",
        label: "Obesity",
        unit: "%",
        range: [15, 50],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.mhlth",
        label: "Poor Mental Health",
        unit: "%",
        range: [8, 25],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.phlth",
        label: "Poor Physical Health",
        unit: "%",
        range: [5, 20],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.bphigh",
        label: "High Blood Pressure",
        unit: "%",
        range: [15, 45],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.casthma",
        label: "Asthma",
        unit: "%",
        range: [5, 15],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.chd",
        label: "Heart Disease",
        unit: "%",
        range: [3, 12],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.csmoking",
        label: "Smoking",
        unit: "%",
        range: [10, 30],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.access2",
        label: "Lack of Insurance",
        unit: "%",
        range: [0, 30],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.checkup",
        label: "Routine Checkup",
        unit: "%",
        range: [50, 85],
        highIsBad: false,
        decimals: 1,
      },
      {
        key: "places_measures.dental",
        label: "Dental Visit",
        unit: "%",
        range: [30, 80],
        highIsBad: false,
        decimals: 1,
      },
      {
        key: "places_measures.sleep",
        label: "Short Sleep (<7hrs)",
        unit: "%",
        range: [20, 50],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.lpa",
        label: "Physical Inactivity",
        unit: "%",
        range: [15, 45],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "places_measures.binge",
        label: "Binge Drinking",
        unit: "%",
        range: [10, 25],
        highIsBad: true,
        decimals: 1,
      },
    ],
  },
  {
    name: "Environmental (EPA)",
    description: "EPA EJScreen indicators",
    metrics: [
      {
        key: "epa_data.pm25",
        label: "PM2.5",
        unit: "ug/m3",
        range: [4, 15],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "epa_data.ozone",
        label: "Ozone",
        unit: "ppb",
        range: [30, 55],
        highIsBad: true,
        decimals: 1,
      },
      {
        key: "epa_data.lead_paint_pct",
        label: "Lead Paint",
        unit: "%",
        range: [0, 0.8],
        highIsBad: true,
        decimals: 2,
      },
      {
        key: "epa_data.air_toxics_cancer_risk",
        label: "Air Toxics Cancer Risk",
        unit: "per million",
        range: [10, 60],
        highIsBad: true,
        decimals: 0,
      },
      {
        key: "epa_data.traffic_proximity",
        label: "Traffic Proximity",
        unit: "veh/day/dist",
        range: [0, 500],
        highIsBad: true,
        decimals: 0,
      },
      {
        key: "epa_data.superfund_proximity",
        label: "Superfund Proximity",
        unit: "score",
        range: [0, 2],
        highIsBad: true,
        decimals: 2,
      },
    ],
  },
];

/**
 * Get all metrics as a flat list.
 */
export function getAllMetrics(): MetricConfig[] {
  return METRIC_CATEGORIES.flatMap((cat) => cat.metrics);
}

/**
 * Find a metric config by its key.
 */
export function getMetricConfig(key: string): MetricConfig | undefined {
  return getAllMetrics().find((m) => m.key === key);
}

/**
 * Get the color for a value given a metric's configuration.
 * Returns one of 5 colors from the appropriate sequential scale.
 */
export function getColorForValue(value: number | null, metric: MetricConfig): string {
  if (value == null) return "#D6D3D1"; // stone-300 for missing data
  const colors = metric.highIsBad ? NEGATIVE_COLORS : POSITIVE_COLORS;
  const [min, max] = metric.range;
  const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const index = Math.min(4, Math.floor(normalized * 5));
  return colors[index];
}

/**
 * Get the color stops array for a metric (for map layer interpolation).
 */
export function getColorStops(metric: MetricConfig): [number, string][] {
  const colors = metric.highIsBad ? NEGATIVE_COLORS : POSITIVE_COLORS;
  const [min, max] = metric.range;
  const step = (max - min) / 4;
  return colors.map((color, i) => [min + step * i, color]);
}

/**
 * Generate legend items for the current metric.
 */
export function getLegendItems(metric: MetricConfig): { color: string; label: string }[] {
  const colors = metric.highIsBad ? NEGATIVE_COLORS : POSITIVE_COLORS;
  const [min, max] = metric.range;
  const step = (max - min) / 4;

  return colors.map((color, i) => {
    const low = min + step * i;
    const high = i < 4 ? min + step * (i + 1) : max;
    const fmt = (v: number) => {
      if (metric.unit === "$") return `$${v.toLocaleString()}`;
      return v.toFixed(metric.decimals);
    };
    return {
      color,
      label: `${fmt(low)} – ${fmt(high)}`,
    };
  });
}
