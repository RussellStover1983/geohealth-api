/**
 * API response types for GeoHealth API.
 * These mirror the Pydantic models from the backend.
 * TODO: Auto-generate from OpenAPI spec using openapi-typescript
 */

export interface LocationModel {
  lat: number;
  lng: number;
  matched_address: string;
}

export interface TractDataModel {
  geoid: string;
  state_fips: string;
  county_fips: string;
  tract_code: string;
  name: string | null;
  total_population: number | null;
  median_household_income: number | null;
  poverty_rate: number | null;
  uninsured_rate: number | null;
  unemployment_rate: number | null;
  median_age: number | null;
  svi_themes: SviThemes | null;
  places_measures: PlacesMeasures | null;
  sdoh_index: number | null;
  epa_data: EpaData | null;
  [key: string]: unknown;
}

export interface SviThemes {
  rpl_theme1: number | null;
  rpl_theme2: number | null;
  rpl_theme3: number | null;
  rpl_theme4: number | null;
  rpl_themes: number | null;
}

export interface PlacesMeasures {
  diabetes: number | null;
  obesity: number | null;
  mhlth: number | null;
  phlth: number | null;
  bphigh: number | null;
  casthma: number | null;
  chd: number | null;
  csmoking: number | null;
  access2: number | null;
  checkup: number | null;
  dental: number | null;
  sleep: number | null;
  lpa: number | null;
  binge: number | null;
  [key: string]: number | null;
}

export interface EpaData {
  pm25: number | null;
  ozone: number | null;
  diesel_pm: number | null;
  air_toxics_cancer_risk: number | null;
  respiratory_hazard_index: number | null;
  traffic_proximity: number | null;
  lead_paint_pct: number | null;
  superfund_proximity: number | null;
  rmp_proximity: number | null;
  hazardous_waste_proximity: number | null;
  wastewater_discharge: number | null;
  _source?: string;
  [key: string]: number | string | null | undefined;
}

export interface ContextResponse {
  location: LocationModel;
  tract: TractDataModel | null;
  narrative: string | null;
  data: TractDataModel | null;
}

export interface NearbyTract {
  geoid: string;
  name: string | null;
  distance_miles: number;
  total_population: number | null;
  median_household_income: number | null;
  poverty_rate: number | null;
  uninsured_rate: number | null;
  unemployment_rate: number | null;
  median_age: number | null;
  sdoh_index: number | null;
}

export interface NearbyResponse {
  center: { lat: number; lng: number };
  radius_miles: number;
  count: number;
  total: number;
  offset: number;
  limit: number;
  tracts: NearbyTract[];
}

export interface TrendYearData {
  year: number;
  total_population: number | null;
  median_household_income: number | null;
  poverty_rate: number | null;
  uninsured_rate: number | null;
  unemployment_rate: number | null;
  median_age: number | null;
}

export interface TrendChange {
  metric: string;
  earliest_year: number | null;
  latest_year: number | null;
  earliest_value: number | null;
  latest_value: number | null;
  absolute_change: number | null;
  percent_change: number | null;
}

export interface TrendsResponse {
  geoid: string;
  name: string | null;
  years: TrendYearData[];
  changes: TrendChange[];
}

export interface DemographicRanking {
  metric: string;
  value: number | null;
  county_percentile: number | null;
  state_percentile: number | null;
  national_percentile: number | null;
}

export interface DemographicAverages {
  metric: string;
  tract_value: number | null;
  county_avg: number | null;
  state_avg: number | null;
  national_avg: number | null;
}

export interface DemographicCompareResponse {
  geoid: string;
  name: string | null;
  state_fips: string;
  county_fips: string;
  rankings: DemographicRanking[];
  averages: DemographicAverages[];
}

export interface FieldDefinition {
  name: string;
  type: string;
  source: string;
  category: string;
  description: string;
  clinical_relevance: string;
  unit: string | null;
  typical_range: string | null;
  example_value: number | string | null;
}

export interface DictionaryCategory {
  category: string;
  description: string;
  source: string;
  fields: FieldDefinition[];
}

export interface DictionaryResponse {
  total_fields: number;
  categories: DictionaryCategory[];
}

export interface HealthResponse {
  status: string;
  database: string;
  detail?: string;
  cache?: { size: number; max_size: number; hit_rate: number };
  rate_limiter?: { active_keys: number };
  uptime_seconds?: number;
}

export interface ErrorResponse {
  error: boolean;
  status_code: number;
  detail: string;
}

// ---------------------------------------------------------------------------
// DPC Market Fit types
// ---------------------------------------------------------------------------

export type ScoreCategory = "WEAK" | "MODERATE" | "STRONG" | "EXCELLENT";

export interface DimensionScore {
  score: number;
  category: ScoreCategory;
  summary: string;
  data_completeness: number;
}

export interface CompositeScore {
  value: number;
  percentile: number | null;
  category: ScoreCategory;
  weights_used: Record<string, number>;
}

export interface ResolvedLocation {
  input: string;
  resolved_lat: number | null;
  resolved_lon: number | null;
  primary_tract_fips: string | null;
  tracts_in_radius: string[];
  radius_miles: number;
  market_population: number | null;
}

export interface DpcDataVintage {
  census_acs: string | null;
  cdc_places: string | null;
  cdc_svi: string | null;
  npi: string | null;
  cbp: string | null;
}

export interface MarketFitResponse {
  location: ResolvedLocation;
  composite_score: CompositeScore;
  dimensions: Record<string, DimensionScore>;
  narrative: string | null;
  data_vintage: DpcDataVintage;
}

export interface DemandDetailResponse {
  location: ResolvedLocation;
  total_population: number | null;
  working_age_population: number | null;
  uninsured_rate: number | null;
  uninsured_count: number | null;
  employer_insured_rate: number | null;
  medicaid_rate: number | null;
  medicare_rate: number | null;
  median_household_income: number | null;
  chronic_disease_prevalence: {
    diabetes_pct: number | null;
    hypertension_pct: number | null;
    obesity_pct: number | null;
    copd_pct: number | null;
    depression_pct: number | null;
    asthma_pct: number | null;
  } | null;
  svi_composite: number | null;
  demand_score: DimensionScore | null;
  affordability_score: DimensionScore | null;
  data_vintage: DpcDataVintage;
}

export interface SupplyDetailResponse {
  location: ResolvedLocation;
  pcp_count: number;
  pcp_per_100k: number | null;
  national_benchmark_pcp_per_100k: number;
  is_hpsa: boolean;
  hpsa_score: number | null;
  hpsa_type: string | null;
  fqhc_count: number;
  urgent_care_count: number;
  rural_health_clinic_count: number;
  supply_gap_score: DimensionScore | null;
  data_vintage: DpcDataVintage;
}
