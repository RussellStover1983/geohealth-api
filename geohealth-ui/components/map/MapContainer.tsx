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

/**
 * Approximate bounding boxes for the 4 loaded states.
 * Used to detect which states are visible in the viewport.
 */
const STATE_BOUNDS: Record<string, { minLat: number; maxLat: number; minLng: number; maxLng: number; fips: string }> = {
  GA: { minLat: 30.36, maxLat: 35.0, minLng: -85.61, maxLng: -80.84, fips: "13" },
  KS: { minLat: 36.99, maxLat: 40.0, minLng: -102.05, maxLng: -94.59, fips: "20" },
  MN: { minLat: 43.5, maxLat: 49.38, minLng: -97.24, maxLng: -89.49, fips: "27" },
  MO: { minLat: 35.99, maxLat: 40.61, minLng: -95.77, maxLng: -89.1, fips: "29" },
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

  // Auto-load states when they become visible in the viewport
  const loadingRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current.getMap();
    if (!map) return;

    const bounds = map.getBounds();
    if (!bounds) return;

    const sw = bounds.getSouthWest();
    const ne = bounds.getNorthEast();

    for (const [, state] of Object.entries(STATE_BOUNDS)) {
      // Check if the state's bounding box overlaps the viewport
      const overlaps =
        state.minLat <= ne.lat &&
        state.maxLat >= sw.lat &&
        state.minLng <= ne.lng &&
        state.maxLng >= sw.lng;

      if (overlaps && !loadedStates.has(state.fips) && !loadingRef.current.has(state.fips)) {
        loadingRef.current.add(state.fips);
        api
          .tractsGeoJSON({ state_fips: state.fips, limit: 2000 })
          .then((geojson) => {
            mergeTractsGeoJSON(geojson, state.fips);
          })
          .catch(() => {
            // Silently fail — user can retry by panning
          })
          .finally(() => {
            loadingRef.current.delete(state.fips);
          });
      }
    }
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
              Coverage: Georgia, Kansas, Minnesota, Missouri
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
