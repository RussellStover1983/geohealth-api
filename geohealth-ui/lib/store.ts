import { create } from "zustand";
import type { TractDataModel } from "./api/types";
import { computeDpcEstimate } from "./map/dpc-score";

export interface ViewportState {
  latitude: number;
  longitude: number;
  zoom: number;
}

interface GeoHealthStore {
  // Map state
  viewport: ViewportState;
  setViewport: (v: Partial<ViewportState>) => void;
  flyToTarget: ViewportState | null;
  flyTo: (target: ViewportState) => void;
  clearFlyTo: () => void;

  // Active SDOH layer for choropleth
  activeLayer: string;
  setActiveLayer: (layer: string) => void;

  // Selected tract (from context lookup or map click)
  selectedTract: TractDataModel | null;
  selectedNarrative: string | null;
  setSelectedTract: (tract: TractDataModel | null, narrative?: string | null) => void;

  // Tract boundaries GeoJSON (for polygon rendering)
  tractsGeoJSON: GeoJSON.FeatureCollection | null;
  loadedStates: Set<string>;
  setTractsGeoJSON: (geojson: GeoJSON.FeatureCollection | null) => void;
  mergeTractsGeoJSON: (geojson: GeoJSON.FeatureCollection, stateFips: string) => void;

  // Search location marker
  searchLocation: { lat: number; lng: number } | null;
  setSearchLocation: (loc: { lat: number; lng: number } | null) => void;

  // UI state
  isDetailPanelOpen: boolean;
  isSidebarCollapsed: boolean;
  isComparisonOpen: boolean;
  toggleDetailPanel: () => void;
  openDetailPanel: () => void;
  closeDetailPanel: () => void;
  toggleSidebar: () => void;
  setComparisonOpen: (open: boolean) => void;

  // Search
  searchQuery: string;
  isSearching: boolean;
  setSearchQuery: (q: string) => void;
  setIsSearching: (v: boolean) => void;
}

export const useGeoHealthStore = create<GeoHealthStore>((set) => ({
  // Initial viewport: centered on continental US
  viewport: {
    latitude: 39.5,
    longitude: -98.35,
    zoom: 4,
  },
  setViewport: (v) =>
    set((state) => ({ viewport: { ...state.viewport, ...v } })),
  flyToTarget: null,
  flyTo: (target) => set({ flyToTarget: target }),
  clearFlyTo: () => set({ flyToTarget: null }),

  activeLayer: "sdoh_index",
  setActiveLayer: (layer) => set({ activeLayer: layer }),

  selectedTract: null,
  selectedNarrative: null,
  setSelectedTract: (tract, narrative = null) =>
    set({
      selectedTract: tract,
      selectedNarrative: narrative ?? null,
      isDetailPanelOpen: tract !== null,
    }),

  tractsGeoJSON: null,
  loadedStates: new Set<string>(),
  setTractsGeoJSON: (geojson) => set({ tractsGeoJSON: geojson }),
  mergeTractsGeoJSON: (geojson, stateFips) =>
    set((state) => {
      if (state.loadedStates.has(stateFips)) return state;
      const newLoadedStates = new Set(state.loadedStates);
      newLoadedStates.add(stateFips);
      const existingFeatures = state.tractsGeoJSON?.features ?? [];
      // Inject DPC Market Fit estimate into each feature's properties
      const enrichedFeatures = geojson.features.map((f) => {
        const props = (f.properties ?? {}) as Record<string, unknown>;
        const dpcScore = computeDpcEstimate(props);
        return {
          ...f,
          properties: { ...props, dpc_market_fit: dpcScore },
        };
      });
      return {
        loadedStates: newLoadedStates,
        tractsGeoJSON: {
          type: "FeatureCollection",
          features: [...existingFeatures, ...enrichedFeatures],
        },
      };
    }),

  searchLocation: null,
  setSearchLocation: (loc) => set({ searchLocation: loc }),

  isDetailPanelOpen: false,
  isSidebarCollapsed: false,
  isComparisonOpen: false,
  toggleDetailPanel: () => set((s) => ({ isDetailPanelOpen: !s.isDetailPanelOpen })),
  openDetailPanel: () => set({ isDetailPanelOpen: true }),
  closeDetailPanel: () => set({ isDetailPanelOpen: false }),
  toggleSidebar: () => set((s) => ({ isSidebarCollapsed: !s.isSidebarCollapsed })),
  setComparisonOpen: (open) => set({ isComparisonOpen: open }),

  searchQuery: "",
  isSearching: false,
  setSearchQuery: (q) => set({ searchQuery: q }),
  setIsSearching: (v) => set({ isSearching: v }),
}));
