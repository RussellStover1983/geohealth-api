import type { NearbyTract } from "@/lib/api/types";
import { getNestedValue } from "@/lib/utils";

/**
 * Build a GeoJSON FeatureCollection of point markers from nearby tracts.
 * Each feature has all available metrics as properties for data-driven styling.
 */
export function buildNearbyGeoJSON(
  tracts: NearbyTract[],
  centerLat: number,
  centerLng: number
): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: tracts.map((tract) => {
      // Approximate position: offset from center based on distance and index
      // Since we don't have actual lat/lng for each tract, use radial placement
      const index = tracts.indexOf(tract);
      const angle = (index / tracts.length) * Math.PI * 2;
      // Convert miles to approximate degrees (~0.0145 degrees per mile)
      const distDeg = tract.distance_miles * 0.0145;
      const lat = centerLat + Math.cos(angle) * distDeg;
      const lng = centerLng + Math.sin(angle) * distDeg;

      return {
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [lng, lat],
        },
        properties: {
          geoid: tract.geoid,
          name: tract.name || `Tract ${tract.geoid}`,
          distance_miles: tract.distance_miles,
          total_population: tract.total_population,
          median_household_income: tract.median_household_income,
          poverty_rate: tract.poverty_rate,
          uninsured_rate: tract.uninsured_rate,
          unemployment_rate: tract.unemployment_rate,
          median_age: tract.median_age,
          sdoh_index: tract.sdoh_index,
        },
      };
    }),
  };
}

/**
 * Build a GeoJSON FeatureCollection of point features from a full tract profile
 * (selected tract from context lookup).
 */
export function buildSelectedTractGeoJSON(
  lat: number,
  lng: number,
  tract: Record<string, unknown>
): GeoJSON.FeatureCollection {
  // Flatten nested objects for map property access
  const props: Record<string, unknown> = { ...tract };

  // Flatten svi_themes
  if (tract.svi_themes && typeof tract.svi_themes === "object") {
    const svi = tract.svi_themes as Record<string, unknown>;
    Object.entries(svi).forEach(([k, v]) => {
      props[`svi_themes.${k}`] = v;
    });
  }

  // Flatten places_measures
  if (tract.places_measures && typeof tract.places_measures === "object") {
    const places = tract.places_measures as Record<string, unknown>;
    Object.entries(places).forEach(([k, v]) => {
      props[`places_measures.${k}`] = v;
    });
  }

  // Flatten epa_data
  if (tract.epa_data && typeof tract.epa_data === "object") {
    const epa = tract.epa_data as Record<string, unknown>;
    Object.entries(epa).forEach(([k, v]) => {
      props[`epa_data.${k}`] = v;
    });
  }

  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [lng, lat] },
        properties: props as GeoJSON.GeoJsonProperties,
      },
    ],
  };
}

/**
 * Get the value of a metric from a tract's properties,
 * supporting dot-notation paths like "svi_themes.rpl_theme1".
 */
export function getTractMetricValue(
  tract: Record<string, unknown>,
  metricKey: string
): number | null {
  return getNestedValue(tract, metricKey);
}
