"""Pydantic response models for OpenAPI documentation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: bool = True
    status_code: int
    detail: str


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    database: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# /v1/context
# ---------------------------------------------------------------------------


class LocationModel(BaseModel):
    lat: float
    lng: float
    matched_address: str


class TractDataModel(BaseModel):
    geoid: str
    state_fips: str
    county_fips: str
    tract_code: str
    name: str | None = None
    total_population: int | None = None
    median_household_income: float | None = None
    poverty_rate: float | None = None
    uninsured_rate: float | None = None
    unemployment_rate: float | None = None
    median_age: float | None = None
    svi_themes: dict | None = None
    places_measures: dict | None = None
    sdoh_index: float | None = None

    model_config = {"extra": "allow"}


class ContextResponse(BaseModel):
    location: LocationModel
    tract: TractDataModel | None = None
    narrative: str | None = None
    data: TractDataModel | None = None


# ---------------------------------------------------------------------------
# /v1/batch
# ---------------------------------------------------------------------------


class BatchResultLocation(BaseModel):
    lat: float
    lng: float
    matched_address: str


class BatchResultItem(BaseModel):
    address: str
    status: str
    location: BatchResultLocation | None = None
    tract: TractDataModel | None = None
    error: str | None = None


class BatchResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchResultItem]


# ---------------------------------------------------------------------------
# /v1/nearby
# ---------------------------------------------------------------------------


class NearbyCenter(BaseModel):
    lat: float
    lng: float


class NearbyTract(BaseModel):
    geoid: str
    name: str | None = None
    distance_miles: float
    total_population: int | None = None
    median_household_income: float | None = None
    poverty_rate: float | None = None
    uninsured_rate: float | None = None
    unemployment_rate: float | None = None
    median_age: float | None = None
    sdoh_index: float | None = None


class NearbyResponse(BaseModel):
    center: NearbyCenter
    radius_miles: float
    count: int
    total: int
    offset: int
    limit: int
    tracts: list[NearbyTract]


# ---------------------------------------------------------------------------
# /v1/compare
# ---------------------------------------------------------------------------


class CompareValues(BaseModel):
    total_population: float | None = None
    median_household_income: float | None = None
    poverty_rate: float | None = None
    uninsured_rate: float | None = None
    unemployment_rate: float | None = None
    median_age: float | None = None
    sdoh_index: float | None = None


class CompareSide(BaseModel):
    type: str
    geoid: str | None = None
    label: str
    values: CompareValues


class CompareDifferences(BaseModel):
    total_population: float | None = None
    median_household_income: float | None = None
    poverty_rate: float | None = None
    uninsured_rate: float | None = None
    unemployment_rate: float | None = None
    median_age: float | None = None
    sdoh_index: float | None = None


class CompareResponse(BaseModel):
    a: CompareSide
    b: CompareSide
    differences: CompareDifferences


# ---------------------------------------------------------------------------
# /v1/stats
# ---------------------------------------------------------------------------


class StateCount(BaseModel):
    state_fips: str
    tract_count: int


class StatsResponse(BaseModel):
    total_states: int
    total_tracts: int
    offset: int
    limit: int
    states: list[StateCount]
