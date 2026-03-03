/**
 * Client-side DPC Market Fit estimate from GeoJSON tract properties.
 *
 * Computes Demand and Affordability dimensions from data already in the
 * GeoJSON. Supply Gap, Employer, and Competition use a neutral placeholder
 * (50) since they require NPI/CBP data not available in the tile properties.
 * Full 5-dimension score is shown on tract click via DpcMarketFitCard.
 */

/** Helper: clamp and normalize a value to 0-100 within [min, max]. */
function normalize(value: number, min: number, max: number): number {
  if (max === min) return 50;
  return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
}

/** Helper: invert a 0-100 score (high raw value = low score). */
function invert(score: number): number {
  return 100 - score;
}

/** Resolve a possibly nested property like "places_measures.diabetes". */
function getNestedProp(props: Record<string, unknown>, key: string): number | null {
  const parts = key.split(".");
  let current: unknown = props;
  for (const part of parts) {
    if (current == null || typeof current !== "object") return null;
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "number" ? current : null;
}

/**
 * Compute a DPC Market Fit estimate (0-100) from GeoJSON feature properties.
 * Returns null if insufficient data is available.
 */
export function computeDpcEstimate(props: Record<string, unknown>): number | null {
  // --- Demand dimension (weight 0.25) ---
  const demandIndicators: { score: number; weight: number }[] = [];

  const uninsuredRate = getNestedProp(props, "uninsured_rate");
  if (uninsuredRate != null) {
    let s = normalize(uninsuredRate, 2, 40);
    if (uninsuredRate > 35) s *= 0.8;
    demandIndicators.push({ score: s, weight: 0.25 });
  }

  const diabetes = getNestedProp(props, "places_measures.diabetes");
  const obesity = getNestedProp(props, "places_measures.obesity");
  if (diabetes != null && obesity != null) {
    const burden = (diabetes + obesity) / 2;
    demandIndicators.push({ score: normalize(burden, 5, 35), weight: 0.25 });
  }

  const sviSES = getNestedProp(props, "svi_themes.rpl_theme1");
  if (sviSES != null) {
    demandIndicators.push({ score: normalize(sviSES, 0, 1), weight: 0.15 });
  }

  const totalPop = getNestedProp(props, "total_population");
  if (totalPop != null) {
    demandIndicators.push({ score: normalize(totalPop, 500, 10000), weight: 0.15 });
  }

  if (demandIndicators.length === 0) return null;

  const demandScore = weightedAvg(demandIndicators);

  // --- Affordability dimension (weight 0.20) ---
  const affordIndicators: { score: number; weight: number }[] = [];

  const income = getNestedProp(props, "median_household_income");
  if (income != null) {
    affordIndicators.push({ score: normalize(income, 15000, 150000), weight: 0.35 });
  }

  const povertyRate = getNestedProp(props, "poverty_rate");
  if (povertyRate != null) {
    affordIndicators.push({ score: invert(normalize(povertyRate, 0, 40)), weight: 0.30 });
  }

  const unemploymentRate = getNestedProp(props, "unemployment_rate");
  if (unemploymentRate != null) {
    affordIndicators.push({
      score: invert(normalize(unemploymentRate, 0, 25)),
      weight: 0.20,
    });
  }

  const affordScore = affordIndicators.length > 0 ? weightedAvg(affordIndicators) : 50;

  // Composite: demand * 0.25 + affordability * 0.20 + neutral placeholders for
  // supply_gap (0.25 * 50), employer (0.20 * 50), competition (0.10 * 50)
  // Neutral contributions = 0.25*50 + 0.20*50 + 0.10*50 = 27.5
  const composite = demandScore * 0.25 + affordScore * 0.20 + 27.5;
  return Math.round(Math.max(0, Math.min(100, composite)) * 10) / 10;
}

function weightedAvg(items: { score: number; weight: number }[]): number {
  const totalWeight = items.reduce((s, i) => s + i.weight, 0);
  if (totalWeight === 0) return 0;
  return items.reduce((s, i) => s + i.score * i.weight, 0) / totalWeight;
}
