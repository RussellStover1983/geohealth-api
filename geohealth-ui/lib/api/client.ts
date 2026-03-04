import type {
  ContextResponse,
  NearbyResponse,
  TrendsResponse,
  DemographicCompareResponse,
  DictionaryResponse,
  HealthResponse,
  ErrorResponse,
  MarketFitResponse,
  DemandDetailResponse,
  SupplyDetailResponse,
  ProvidersResponse,
} from "./types";

/**
 * API base URL resolution:
 *
 * By default, all requests go through the Next.js BFF proxy at /api/geohealth/...
 * which injects the API key server-side. The real key never reaches the browser.
 *
 * If NEXT_PUBLIC_API_URL is set, requests go directly to that URL instead
 * (useful for local development with NEXT_PUBLIC_API_KEY).
 */
const USE_PROXY = !process.env.NEXT_PUBLIC_API_URL;
const API_BASE = USE_PROXY ? "/api/geohealth" : process.env.NEXT_PUBLIC_API_URL!;
const DIRECT_API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, API_BASE.startsWith("/") ? window.location.origin : API_BASE);

  // When using proxy, the path needs to be /api/geohealth + original path
  if (USE_PROXY) {
    url.pathname = `/api/geohealth${path}`;
  }

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const headers: Record<string, string> = {
    "Accept": "application/json",
  };

  // Only send API key directly if not using the proxy
  if (!USE_PROXY && DIRECT_API_KEY) {
    headers["X-API-Key"] = DIRECT_API_KEY;
  }

  const response = await fetch(url.toString(), { headers });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errorBody = (await response.json()) as ErrorResponse;
      detail = errorBody.detail || detail;
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

/**
 * DPC Market Fit API fetch — routes through /api/dpc proxy.
 */
const DPC_BASE = process.env.NEXT_PUBLIC_DPC_API_URL || "";
const USE_DPC_PROXY = !DPC_BASE;

async function dpcFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  let url: URL;
  if (USE_DPC_PROXY) {
    url = new URL(`/api/dpc${path}`, window.location.origin);
  } else {
    url = new URL(path, DPC_BASE);
  }

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errorBody = (await response.json()) as ErrorResponse;
      detail = errorBody.detail || detail;
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/health");
  },

  context(params: {
    address?: string;
    lat?: number;
    lng?: number;
    narrative?: boolean;
    state_fips?: string;
  }): Promise<ContextResponse> {
    const searchParams: Record<string, string> = {};
    if (params.address) searchParams.address = params.address;
    if (params.lat !== undefined) searchParams.lat = params.lat.toString();
    if (params.lng !== undefined) searchParams.lng = params.lng.toString();
    if (params.narrative) searchParams.narrative = "true";
    if (params.state_fips) searchParams.state_fips = params.state_fips;
    return apiFetch<ContextResponse>("/v1/context", searchParams);
  },

  nearby(params: {
    lat: number;
    lng: number;
    radius?: number;
    limit?: number;
    offset?: number;
  }): Promise<NearbyResponse> {
    const searchParams: Record<string, string> = {
      lat: params.lat.toString(),
      lng: params.lng.toString(),
    };
    if (params.radius !== undefined) searchParams.radius = params.radius.toString();
    if (params.limit !== undefined) searchParams.limit = params.limit.toString();
    if (params.offset !== undefined) searchParams.offset = params.offset.toString();
    return apiFetch<NearbyResponse>("/v1/nearby", searchParams);
  },

  tractsGeoJSON(params: {
    state_fips?: string;
    lat?: number;
    lng?: number;
    radius?: number;
    limit?: number;
    simplify?: number;
  }): Promise<GeoJSON.FeatureCollection> {
    const searchParams: Record<string, string> = {};
    if (params.state_fips) searchParams.state_fips = params.state_fips;
    if (params.lat !== undefined) searchParams.lat = params.lat.toString();
    if (params.lng !== undefined) searchParams.lng = params.lng.toString();
    if (params.radius !== undefined) searchParams.radius = params.radius.toString();
    if (params.limit !== undefined) searchParams.limit = params.limit.toString();
    if (params.simplify !== undefined) searchParams.simplify = params.simplify.toString();
    return apiFetch<GeoJSON.FeatureCollection>("/v1/tracts/geojson", searchParams);
  },

  trends(geoid: string): Promise<TrendsResponse> {
    return apiFetch<TrendsResponse>("/v1/trends", { geoid });
  },

  demographicCompare(geoid: string): Promise<DemographicCompareResponse> {
    return apiFetch<DemographicCompareResponse>("/v1/demographics/compare", { geoid });
  },

  dictionary(): Promise<DictionaryResponse> {
    return apiFetch<DictionaryResponse>("/v1/dictionary");
  },

  // DPC Market Fit endpoints (via /api/dpc proxy)
  marketFit(params: {
    tract_fips?: string;
    address?: string;
    lat?: number;
    lon?: number;
    zip_code?: string;
    radius_miles?: number;
  }): Promise<MarketFitResponse> {
    const searchParams: Record<string, string> = {};
    if (params.tract_fips) searchParams.tract_fips = params.tract_fips;
    if (params.address) searchParams.address = params.address;
    if (params.lat !== undefined) searchParams.lat = params.lat.toString();
    if (params.lon !== undefined) searchParams.lon = params.lon.toString();
    if (params.zip_code) searchParams.zip_code = params.zip_code;
    if (params.radius_miles !== undefined) searchParams.radius_miles = params.radius_miles.toString();
    return dpcFetch<MarketFitResponse>("/api/v1/market-fit", searchParams);
  },

  marketFitDemand(params: {
    tract_fips?: string;
    address?: string;
  }): Promise<DemandDetailResponse> {
    const searchParams: Record<string, string> = {};
    if (params.tract_fips) searchParams.tract_fips = params.tract_fips;
    if (params.address) searchParams.address = params.address;
    return dpcFetch<DemandDetailResponse>("/api/v1/market-fit/demand", searchParams);
  },

  marketFitSupply(params: {
    tract_fips?: string;
    address?: string;
  }): Promise<SupplyDetailResponse> {
    const searchParams: Record<string, string> = {};
    if (params.tract_fips) searchParams.tract_fips = params.tract_fips;
    if (params.address) searchParams.address = params.address;
    return dpcFetch<SupplyDetailResponse>("/api/v1/market-fit/supply", searchParams);
  },

  // NPI Provider endpoints
  providersGeoJSON(params: {
    bbox: [number, number, number, number];
    provider_type?: string;
    limit?: number;
  }): Promise<GeoJSON.FeatureCollection> {
    const searchParams: Record<string, string> = {
      bbox: params.bbox.join(","),
    };
    if (params.provider_type && params.provider_type !== "all") {
      searchParams.provider_type = params.provider_type;
    }
    if (params.limit !== undefined) searchParams.limit = params.limit.toString();
    return apiFetch<GeoJSON.FeatureCollection>("/v1/providers/geojson", searchParams);
  },

  providers(params: {
    lat?: number;
    lng?: number;
    radius?: number;
    tract_fips?: string;
    provider_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<ProvidersResponse> {
    const searchParams: Record<string, string> = {};
    if (params.lat !== undefined) searchParams.lat = params.lat.toString();
    if (params.lng !== undefined) searchParams.lng = params.lng.toString();
    if (params.radius !== undefined) searchParams.radius = params.radius.toString();
    if (params.tract_fips) searchParams.tract_fips = params.tract_fips;
    if (params.provider_type && params.provider_type !== "all") {
      searchParams.provider_type = params.provider_type;
    }
    if (params.limit !== undefined) searchParams.limit = params.limit.toString();
    if (params.offset !== undefined) searchParams.offset = params.offset.toString();
    return apiFetch<ProvidersResponse>("/v1/providers", searchParams);
  },
};

export { ApiError };
