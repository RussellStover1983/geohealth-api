"use client";

import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import Map, {
  NavigationControl,
  GeolocateControl,
  Source,
  Layer,
  Popup,
  type MapRef,
  type ViewStateChangeEvent,
  type MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useGeoHealthStore } from "@/lib/store";
import {
  getMetricConfig,
  NEGATIVE_COLORS,
  POSITIVE_COLORS,
} from "@/lib/map/styles";
import { ChoroplethLegend } from "./ChoroplethLegend";
import type { TractDataModel } from "@/lib/api/types";
import { api } from "@/lib/api/client";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

/** Minimum zoom level before auto-loading state tract data */
const MIN_LOAD_ZOOM = 6;

/**
 * Approximate bounding boxes for all 50 states + DC.
 * Used to detect which states are visible in the viewport and auto-load their tract data.
 */
const STATE_BOUNDS: Record<string, { minLat: number; maxLat: number; minLng: number; maxLng: number; fips: string }> = {
  AL: { minLat: 30.22, maxLat: 35.01, minLng: -88.47, maxLng: -84.89, fips: "01" },
  AK: { minLat: 51.21, maxLat: 71.39, minLng: -179.15, maxLng: -129.98, fips: "02" },
  AZ: { minLat: 31.33, maxLat: 37.00, minLng: -114.81, maxLng: -109.04, fips: "04" },
  AR: { minLat: 33.00, maxLat: 36.50, minLng: -94.62, maxLng: -89.64, fips: "05" },
  CA: { minLat: 32.53, maxLat: 42.01, minLng: -124.48, maxLng: -114.13, fips: "06" },
  CO: { minLat: 36.99, maxLat: 41.00, minLng: -109.06, maxLng: -102.04, fips: "08" },
  CT: { minLat: 40.99, maxLat: 42.05, minLng: -73.73, maxLng: -71.79, fips: "09" },
  DE: { minLat: 38.45, maxLat: 39.84, minLng: -75.79, maxLng: -75.05, fips: "10" },
  DC: { minLat: 38.79, maxLat: 38.99, minLng: -77.12, maxLng: -76.91, fips: "11" },
  FL: { minLat: 24.40, maxLat: 31.00, minLng: -87.63, maxLng: -80.03, fips: "12" },
  GA: { minLat: 30.36, maxLat: 35.00, minLng: -85.61, maxLng: -80.84, fips: "13" },
  HI: { minLat: 18.91, maxLat: 22.24, minLng: -160.25, maxLng: -154.81, fips: "15" },
  ID: { minLat: 41.99, maxLat: 49.00, minLng: -117.24, maxLng: -111.04, fips: "16" },
  IL: { minLat: 36.97, maxLat: 42.51, minLng: -91.51, maxLng: -87.49, fips: "17" },
  IN: { minLat: 37.77, maxLat: 41.76, minLng: -88.10, maxLng: -84.78, fips: "18" },
  IA: { minLat: 40.38, maxLat: 43.50, minLng: -96.64, maxLng: -90.14, fips: "19" },
  KS: { minLat: 36.99, maxLat: 40.00, minLng: -102.05, maxLng: -94.59, fips: "20" },
  KY: { minLat: 36.50, maxLat: 39.15, minLng: -89.57, maxLng: -81.96, fips: "21" },
  LA: { minLat: 28.93, maxLat: 33.02, minLng: -94.04, maxLng: -88.82, fips: "22" },
  ME: { minLat: 43.06, maxLat: 47.46, minLng: -71.08, maxLng: -66.95, fips: "23" },
  MD: { minLat: 37.91, maxLat: 39.72, minLng: -79.49, maxLng: -75.05, fips: "24" },
  MA: { minLat: 41.24, maxLat: 42.89, minLng: -73.51, maxLng: -69.93, fips: "25" },
  MI: { minLat: 41.70, maxLat: 48.31, minLng: -90.42, maxLng: -82.12, fips: "26" },
  MN: { minLat: 43.50, maxLat: 49.38, minLng: -97.24, maxLng: -89.49, fips: "27" },
  MS: { minLat: 30.17, maxLat: 34.99, minLng: -91.66, maxLng: -88.10, fips: "28" },
  MO: { minLat: 35.99, maxLat: 40.61, minLng: -95.77, maxLng: -89.10, fips: "29" },
  MT: { minLat: 44.36, maxLat: 49.00, minLng: -116.05, maxLng: -104.04, fips: "30" },
  NE: { minLat: 39.99, maxLat: 43.00, minLng: -104.05, maxLng: -95.31, fips: "31" },
  NV: { minLat: 35.00, maxLat: 42.00, minLng: -120.01, maxLng: -114.04, fips: "32" },
  NH: { minLat: 42.70, maxLat: 45.31, minLng: -72.56, maxLng: -70.61, fips: "33" },
  NJ: { minLat: 38.93, maxLat: 41.36, minLng: -75.56, maxLng: -73.89, fips: "34" },
  NM: { minLat: 31.33, maxLat: 37.00, minLng: -109.05, maxLng: -103.00, fips: "35" },
  NY: { minLat: 40.50, maxLat: 45.02, minLng: -79.76, maxLng: -71.86, fips: "36" },
  NC: { minLat: 33.84, maxLat: 36.59, minLng: -84.32, maxLng: -75.46, fips: "37" },
  ND: { minLat: 45.94, maxLat: 49.00, minLng: -104.05, maxLng: -96.55, fips: "38" },
  OH: { minLat: 38.40, maxLat: 41.98, minLng: -84.82, maxLng: -80.52, fips: "39" },
  OK: { minLat: 33.62, maxLat: 37.00, minLng: -103.00, maxLng: -94.43, fips: "40" },
  OR: { minLat: 41.99, maxLat: 46.29, minLng: -124.57, maxLng: -116.46, fips: "41" },
  PA: { minLat: 39.72, maxLat: 42.27, minLng: -80.52, maxLng: -74.69, fips: "42" },
  RI: { minLat: 41.15, maxLat: 42.02, minLng: -71.86, maxLng: -71.12, fips: "44" },
  SC: { minLat: 32.03, maxLat: 35.22, minLng: -83.35, maxLng: -78.54, fips: "45" },
  SD: { minLat: 42.48, maxLat: 45.95, minLng: -104.06, maxLng: -96.44, fips: "46" },
  TN: { minLat: 34.98, maxLat: 36.68, minLng: -90.31, maxLng: -81.65, fips: "47" },
  TX: { minLat: 25.84, maxLat: 36.50, minLng: -106.65, maxLng: -93.51, fips: "48" },
  UT: { minLat: 36.99, maxLat: 42.00, minLng: -114.05, maxLng: -109.04, fips: "49" },
  VT: { minLat: 42.73, maxLat: 45.02, minLng: -73.44, maxLng: -71.46, fips: "50" },
  VA: { minLat: 36.54, maxLat: 39.47, minLng: -83.68, maxLng: -75.24, fips: "51" },
  WA: { minLat: 45.54, maxLat: 49.00, minLng: -124.85, maxLng: -116.92, fips: "53" },
  WV: { minLat: 37.20, maxLat: 40.64, minLng: -82.64, maxLng: -77.72, fips: "54" },
  WI: { minLat: 42.49, maxLat: 47.31, minLng: -92.89, maxLng: -86.25, fips: "55" },
  WY: { minLat: 40.99, maxLat: 45.01, minLng: -111.06, maxLng: -104.05, fips: "56" },
};

interface HoveredFeature {
  lng: number;
  lat: number;
  name: string;
  value: number | null;
  geoid: string;
}

export function MapContainer() {
  const mapRef = useRef<MapRef>(null);
  const {
    viewport,
    setViewport,
    flyToTarget,
    clearFlyTo,
    activeLayer,
    tractsGeoJSON,
    searchLocation,
    setSelectedTract,
    loadedStates,
    mergeTractsGeoJSON,
  } = useGeoHealthStore();

  const [hoveredFeature, setHoveredFeature] = useState<HoveredFeature | null>(
    null
  );
  const [hoveredGeoid, setHoveredGeoid] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string>("grab");
  const [isLoadingTracts, setIsLoadingTracts] = useState(false);

  // Fly to target when it changes
  useEffect(() => {
    if (flyToTarget && mapRef.current) {
      mapRef.current.flyTo({
        center: [flyToTarget.longitude, flyToTarget.latitude],
        zoom: flyToTarget.zoom,
        duration: 2000,
        essential: true,
      });
      clearFlyTo();
    }
  }, [flyToTarget, clearFlyTo]);

  // Auto-load states when they become visible in the viewport (debounced, zoom-gated)
  const loadingRef = useRef<Set<string>>(new Set());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Debounce: wait 300ms after the last viewport change before checking
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (!mapRef.current) return;
      const map = mapRef.current.getMap();
      if (!map) return;

      // Don't load tract data when zoomed out too far
      if (viewport.zoom < MIN_LOAD_ZOOM) return;

      const bounds = map.getBounds();
      if (!bounds) return;

      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();

      // Use simplified geometry when zoomed out, full detail when zoomed in
      const simplify = viewport.zoom < 9 ? 0.001 : 0;

      for (const [, state] of Object.entries(STATE_BOUNDS)) {
        const overlaps =
          state.minLat <= ne.lat &&
          state.maxLat >= sw.lat &&
          state.minLng <= ne.lng &&
          state.maxLng >= sw.lng;

        if (overlaps && !loadedStates.has(state.fips) && !loadingRef.current.has(state.fips)) {
          loadingRef.current.add(state.fips);
          setIsLoadingTracts(true);
          api
            .tractsGeoJSON({ state_fips: state.fips, limit: 2000, simplify })
            .then((geojson) => {
              mergeTractsGeoJSON(geojson, state.fips);
            })
            .catch(() => {
              // Silently fail — user can retry by panning
            })
            .finally(() => {
              loadingRef.current.delete(state.fips);
              if (loadingRef.current.size === 0) setIsLoadingTracts(false);
            });
        }
      }
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [viewport, loadedStates, mergeTractsGeoJSON]);

  const onMove = useCallback(
    (evt: ViewStateChangeEvent) => {
      setViewport({
        latitude: evt.viewState.latitude,
        longitude: evt.viewState.longitude,
        zoom: evt.viewState.zoom,
      });
    },
    [setViewport]
  );

  // Get metric config for color computation
  const metricConfig = getMetricConfig(activeLayer);
  const colors = metricConfig
    ? metricConfig.highIsBad
      ? NEGATIVE_COLORS
      : POSITIVE_COLORS
    : POSITIVE_COLORS;

  const onMouseEnter = useCallback(
    (e: MapLayerMouseEvent) => {
      setCursor("pointer");
      if (e.features && e.features[0]) {
        const props = e.features[0].properties;
        if (!props) return;
        const coords = e.lngLat;
        const value =
          metricConfig && props[activeLayer] != null
            ? (props[activeLayer] as number)
            : null;
        setHoveredFeature({
          lng: coords.lng,
          lat: coords.lat,
          name: (props.name as string) || `Tract ${props.geoid}`,
          value,
          geoid: props.geoid as string,
        });
        setHoveredGeoid(props.geoid as string);
      }
    },
    [activeLayer, metricConfig]
  );

  const onMouseLeave = useCallback(() => {
    setCursor("grab");
    setHoveredFeature(null);
    setHoveredGeoid(null);
  }, []);

  const onClick = useCallback(
    (e: MapLayerMouseEvent) => {
      if (e.features && e.features[0]) {
        const props = e.features[0].properties;
        if (!props) return;

        // Build tract data from GeoJSON properties
        const tractData = {
          geoid: props.geoid as string,
          state_fips: props.state_fips as string,
          county_fips: props.county_fips as string,
          tract_code: props.tract_code as string,
          name: (props.name as string) || null,
          total_population: props.total_population as number | null,
          median_household_income:
            props.median_household_income as number | null,
          poverty_rate: props.poverty_rate as number | null,
          uninsured_rate: props.uninsured_rate as number | null,
          unemployment_rate: props.unemployment_rate as number | null,
          median_age: props.median_age as number | null,
          sdoh_index: props.sdoh_index as number | null,
          // Reconstruct nested objects from flattened keys
          svi_themes: rebuildNestedObject(props, "svi_themes.") as TractDataModel["svi_themes"],
          places_measures: rebuildNestedObject(props, "places_measures.") as TractDataModel["places_measures"],
          epa_data: rebuildNestedObject(props, "epa_data.") as TractDataModel["epa_data"],
        };
        setSelectedTract(tractData as TractDataModel);
      }
    },
    [setSelectedTract]
  );

  // Build MapLibre expression for fill color based on active metric
  const fillColorExpr = metricConfig
    ? ([
        "case",
        ["!", ["has", activeLayer]],
        "#E7E5E4",
        [
          "interpolate",
          ["linear"],
          ["get", activeLayer],
          metricConfig.range[0],
          colors[0],
          metricConfig.range[0] +
            (metricConfig.range[1] - metricConfig.range[0]) * 0.25,
          colors[1],
          metricConfig.range[0] +
            (metricConfig.range[1] - metricConfig.range[0]) * 0.5,
          colors[2],
          metricConfig.range[0] +
            (metricConfig.range[1] - metricConfig.range[0]) * 0.75,
          colors[3],
          metricConfig.range[1],
          colors[4],
        ],
      ] as unknown as string)
    : "#0D9488";

  // Highlight expression for hovered tract
  const lineWidthExpr = hoveredGeoid
    ? ([
        "case",
        ["==", ["get", "geoid"], hoveredGeoid],
        3,
        1,
      ] as unknown as number)
    : 1;

  const lineColorExpr = hoveredGeoid
    ? ([
        "case",
        ["==", ["get", "geoid"], hoveredGeoid],
        "#0F766E",
        "#ffffff",
      ] as unknown as string)
    : "#ffffff";

  return (
    <div className="relative h-full w-full">
      <Map
        ref={mapRef}
        initialViewState={viewport}
        onMove={onMove}
        mapStyle={MAP_STYLE}
        style={{ width: "100%", height: "100%" }}
        cursor={cursor}
        interactiveLayerIds={tractsGeoJSON ? ["tract-fill"] : []}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onClick={onClick}
        attributionControl={true}
        reuseMaps
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        <GeolocateControl position="bottom-right" />

        {/* Tract polygon fill layer */}
        {tractsGeoJSON && (
          <Source id="tract-boundaries" type="geojson" data={tractsGeoJSON}>
            <Layer
              id="tract-fill"
              type="fill"
              paint={{
                "fill-color": fillColorExpr as unknown as string,
                "fill-opacity": 0.7,
              }}
            />
            <Layer
              id="tract-outline"
              type="line"
              paint={{
                "line-color": lineColorExpr as unknown as string,
                "line-width": lineWidthExpr as unknown as number,
                "line-opacity": 0.8,
              }}
            />
          </Source>
        )}

        {/* Search location marker */}
        {searchLocation && (
          <Source
            id="search-marker"
            type="geojson"
            data={{
              type: "FeatureCollection",
              features: [
                {
                  type: "Feature",
                  geometry: {
                    type: "Point",
                    coordinates: [searchLocation.lng, searchLocation.lat],
                  },
                  properties: {},
                },
              ],
            }}
          >
            <Layer
              id="search-marker-outer"
              type="circle"
              paint={{
                "circle-radius": 14,
                "circle-color": "#14B8A6",
                "circle-opacity": 0.25,
              }}
            />
            <Layer
              id="search-marker-inner"
              type="circle"
              paint={{
                "circle-radius": 7,
                "circle-color": "#0D9488",
                "circle-stroke-width": 3,
                "circle-stroke-color": "#ffffff",
              }}
            />
          </Source>
        )}

        {/* Hover popup */}
        {hoveredFeature && (
          <Popup
            longitude={hoveredFeature.lng}
            latitude={hoveredFeature.lat}
            anchor="bottom"
            closeButton={false}
            closeOnClick={false}
            offset={8}
          >
            <div className="text-xs">
              <p className="font-semibold text-stone-900">
                {hoveredFeature.name}
              </p>
              {metricConfig && (
                <p className="text-stone-600">
                  {metricConfig.label}:{" "}
                  <span className="font-medium tabular-nums">
                    {hoveredFeature.value != null
                      ? metricConfig.unit === "$"
                        ? `$${hoveredFeature.value.toLocaleString()}`
                        : `${hoveredFeature.value.toFixed(metricConfig.decimals)}${metricConfig.unit === "%" ? "%" : ""}`
                      : "N/A"}
                  </span>
                </p>
              )}
            </div>
          </Popup>
        )}
      </Map>

      {/* Loading indicator */}
      {isLoadingTracts && (
        <div className="absolute left-1/2 top-4 z-10 -translate-x-1/2">
          <div className="flex items-center gap-2 rounded-full bg-white/90 px-4 py-2 text-xs font-medium text-stone-600 shadow-md backdrop-blur-sm">
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-stone-300 border-t-accent-500" />
            Loading tract data...
          </div>
        </div>
      )}

      {/* Legend overlay */}
      {metricConfig && (
        <div className="absolute bottom-8 left-4 z-10">
          <ChoroplethLegend metric={metricConfig} />
        </div>
      )}

      {/* Empty state overlay */}
      {!searchLocation && !tractsGeoJSON && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="pointer-events-auto rounded-2xl bg-white/90 px-8 py-6 text-center shadow-lg backdrop-blur-sm">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-accent-100">
              <svg
                className="h-6 w-6 text-accent-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                />
              </svg>
            </div>
            <p className="text-sm font-medium text-stone-800">
              Search an address to explore SDOH data
            </p>
            <p className="mt-1 text-xs text-stone-500">
              Coverage: All 50 US states + DC
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Rebuild a nested object from flattened GeoJSON properties.
 * e.g., {"svi_themes.rpl_theme1": 0.35} → {rpl_theme1: 0.35}
 */
function rebuildNestedObject(
  props: Record<string, unknown>,
  prefix: string
): Record<string, unknown> | null {
  const result: Record<string, unknown> = {};
  let found = false;
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith(prefix)) {
      result[key.slice(prefix.length)] = value;
      found = true;
    }
  }
  return found ? result : null;
}
