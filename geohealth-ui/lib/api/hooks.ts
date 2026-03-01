"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { api, ApiError } from "./client";
import type {
  ContextResponse,
  NearbyResponse,
  TrendsResponse,
  DemographicCompareResponse,
  DictionaryResponse,
} from "./types";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  isLoading: boolean;
}

export function useContextLookup() {
  const [state, setState] = useState<AsyncState<ContextResponse>>({
    data: null,
    error: null,
    isLoading: false,
  });

  const lookup = useCallback(async (address: string) => {
    setState({ data: null, error: null, isLoading: true });
    try {
      const data = await api.context({ address, narrative: true });
      setState({ data, error: null, isLoading: false });
      return data;
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to look up address";
      setState({ data: null, error: message, isLoading: false });
      return null;
    }
  }, []);

  const lookupByCoords = useCallback(async (lat: number, lng: number) => {
    setState({ data: null, error: null, isLoading: true });
    try {
      const data = await api.context({ lat, lng, narrative: true });
      setState({ data, error: null, isLoading: false });
      return data;
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to look up location";
      setState({ data: null, error: message, isLoading: false });
      return null;
    }
  }, []);

  return { ...state, lookup, lookupByCoords };
}

export function useNearbyTracts() {
  const [state, setState] = useState<AsyncState<NearbyResponse>>({
    data: null,
    error: null,
    isLoading: false,
  });

  const search = useCallback(async (lat: number, lng: number, radius = 10, limit = 50) => {
    setState({ data: null, error: null, isLoading: true });
    try {
      const data = await api.nearby({ lat, lng, radius, limit });
      setState({ data, error: null, isLoading: false });
      return data;
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to find nearby tracts";
      setState({ data: null, error: message, isLoading: false });
      return null;
    }
  }, []);

  return { ...state, search };
}

export function useTractsGeoJSON() {
  const [state, setState] = useState<AsyncState<GeoJSON.FeatureCollection>>({
    data: null,
    error: null,
    isLoading: false,
  });

  const load = useCallback(
    async (params: {
      state_fips?: string;
      lat?: number;
      lng?: number;
      radius?: number;
      limit?: number;
    }) => {
      setState({ data: null, error: null, isLoading: true });
      try {
        const data = await api.tractsGeoJSON(params);
        setState({ data, error: null, isLoading: false });
        return data;
      } catch (err) {
        const message =
          err instanceof ApiError ? err.detail : "Failed to load tract boundaries";
        setState({ data: null, error: message, isLoading: false });
        return null;
      }
    },
    []
  );

  return { ...state, load };
}

export function useTrends(geoid: string | null) {
  const [state, setState] = useState<AsyncState<TrendsResponse>>({
    data: null,
    error: null,
    isLoading: false,
  });

  useEffect(() => {
    if (!geoid) {
      setState({ data: null, error: null, isLoading: false });
      return;
    }

    let cancelled = false;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    api.trends(geoid).then(
      (data) => {
        if (!cancelled) setState({ data, error: null, isLoading: false });
      },
      (err) => {
        if (!cancelled) {
          const message = err instanceof ApiError ? err.detail : "Failed to load trends";
          setState({ data: null, error: message, isLoading: false });
        }
      }
    );

    return () => { cancelled = true; };
  }, [geoid]);

  return state;
}

export function useDemographicComparison(geoid: string | null) {
  const [state, setState] = useState<AsyncState<DemographicCompareResponse>>({
    data: null,
    error: null,
    isLoading: false,
  });

  useEffect(() => {
    if (!geoid) {
      setState({ data: null, error: null, isLoading: false });
      return;
    }

    let cancelled = false;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    api.demographicCompare(geoid).then(
      (data) => {
        if (!cancelled) setState({ data, error: null, isLoading: false });
      },
      (err) => {
        if (!cancelled) {
          const message = err instanceof ApiError ? err.detail : "Failed to load comparison";
          setState({ data: null, error: message, isLoading: false });
        }
      }
    );

    return () => { cancelled = true; };
  }, [geoid]);

  return state;
}

export function useDataDictionary() {
  const [state, setState] = useState<AsyncState<DictionaryResponse>>({
    data: null,
    error: null,
    isLoading: false,
  });
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;

    setState({ data: null, error: null, isLoading: true });
    api.dictionary().then(
      (data) => setState({ data, error: null, isLoading: false }),
      (err) => {
        const message = err instanceof ApiError ? err.detail : "Failed to load dictionary";
        setState({ data: null, error: message, isLoading: false });
      }
    );
  }, []);

  return state;
}
