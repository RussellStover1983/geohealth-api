"""Pydantic response models for OpenAPI documentation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Structured error returned by all non-2xx responses."""

    error: bool = Field(True, description="Always true for error responses")
    status_code: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable error message")


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class CacheHealth(BaseModel):
    """Cache subsystem status."""

    size: int = Field(..., description="Current number of cached entries")
    max_size: int = Field(..., description="Maximum cache capacity")
    hit_rate: float = Field(..., description="Cache hit rate (0.0–1.0)")


class RateLimiterHealth(BaseModel):
    """Rate limiter subsystem status."""

    active_keys: int = Field(..., description="Number of tracked API key buckets")


class HealthResponse(BaseModel):
    """Health-check result indicating API and database status."""

    status: str = Field(
        ..., description="Overall status: 'ok' or 'degraded'"
    )
    database: str = Field(
        ..., description="Database connectivity: 'connected' or 'unreachable'"
    )
    detail: str | None = Field(
        None, description="Error detail when database is unreachable"
    )
    cache: CacheHealth | None = Field(
        None, description="Cache subsystem health (present when status is ok)"
    )
    rate_limiter: RateLimiterHealth | None = Field(
        None, description="Rate limiter health (present when status is ok)"
    )
    uptime_seconds: float | None = Field(
        None, description="Seconds since the process started"
    )


# ---------------------------------------------------------------------------
# /v1/context
# ---------------------------------------------------------------------------


class LocationModel(BaseModel):
    """Geocoded location returned with every context lookup."""

    lat: float = Field(..., description="Latitude of the matched location")
    lng: float = Field(..., description="Longitude of the matched location")
    matched_address: str = Field(
        ..., description="Address string as matched by the geocoder"
    )


class TractDataModel(BaseModel):
    """Census tract profile with demographics, SVI themes, and health measures.

    Fixed ACS columns are always present. JSONB-backed fields (`svi_themes`,
    `places_measures`) contain nested dictionaries whose keys may grow over
    time without requiring schema changes. The model uses `extra = "allow"`
    so new fields flow through automatically.
    """

    geoid: str = Field(
        ..., description="11-digit census tract GEOID (state + county + tract)"
    )
    state_fips: str = Field(
        ..., description="2-digit state FIPS code"
    )
    county_fips: str = Field(
        ..., description="3-digit county FIPS code"
    )
    tract_code: str = Field(
        ..., description="6-digit census tract code"
    )
    name: str | None = Field(
        None, description="Human-readable tract name"
    )
    total_population: int | None = Field(
        None,
        description=(
            "ACS total population estimate. Small populations (under 1,000) "
            "produce less reliable rate estimates."
        ),
    )
    median_household_income: float | None = Field(
        None,
        description=(
            "ACS median household income in dollars. Incomes below $30,000 "
            "correlate with higher chronic disease rates and delayed care-seeking."
        ),
    )
    poverty_rate: float | None = Field(
        None,
        description=(
            "Percentage of population below the federal poverty level (ACS). "
            "Rates above 20% indicate high-poverty areas associated with increased "
            "chronic disease burden and reduced healthcare access."
        ),
    )
    uninsured_rate: float | None = Field(
        None,
        description=(
            "Percentage of population without health insurance (ACS). Rates above "
            "15% suggest significant access barriers and delayed preventive care."
        ),
    )
    unemployment_rate: float | None = Field(
        None,
        description=(
            "Percentage of civilian labor force unemployed (ACS). Rates above 10% "
            "indicate economic distress, associated with depression and substance use."
        ),
    )
    median_age: float | None = Field(
        None,
        description=(
            "Median age of the population (ACS). Tracts above 45 may have higher "
            "chronic disease prevalence; tracts below 25 may indicate student "
            "populations."
        ),
    )
    svi_themes: dict | None = Field(
        None,
        description=(
            "CDC/ATSDR Social Vulnerability Index theme percentile rankings (0-1). "
            "Keys: rpl_theme1 (socioeconomic), rpl_theme2 (household/disability), "
            "rpl_theme3 (minority/language), rpl_theme4 (housing/transportation), "
            "rpl_themes (overall). Percentiles above 0.75 indicate high "
            "vulnerability relative to all US census tracts."
        ),
    )
    places_measures: dict | None = Field(
        None,
        description=(
            "CDC PLACES health outcome measures (crude prevalence %). Model-based "
            "estimates from BRFSS. Keys: diabetes, obesity, mhlth (mental health), "
            "phlth (physical health), bphigh (blood pressure), casthma (asthma), "
            "chd (coronary heart disease), csmoking (smoking), access2 (no insurance), "
            "checkup, dental, sleep (short sleep), lpa (physical inactivity), "
            "binge (binge drinking)."
        ),
    )
    sdoh_index: float | None = Field(
        None,
        description=(
            "Composite social determinants of health index (0-1 scale). Computed "
            "from poverty, uninsured, unemployment rates and SVI. Values above 0.6 "
            "indicate high social vulnerability warranting intensive care coordination."
        ),
    )

    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "examples": [
                {
                    "geoid": "27053026200",
                    "state_fips": "27",
                    "county_fips": "053",
                    "tract_code": "026200",
                    "name": "Census Tract 262, Hennepin County, MN",
                    "total_population": 4521,
                    "median_household_income": 72500.0,
                    "poverty_rate": 11.3,
                    "uninsured_rate": 5.8,
                    "unemployment_rate": 4.2,
                    "median_age": 34.7,
                    "svi_themes": {
                        "rpl_theme1": 0.35,
                        "rpl_theme2": 0.42,
                        "rpl_theme3": 0.61,
                        "rpl_theme4": 0.28,
                        "rpl_themes": 0.44,
                    },
                    "places_measures": {
                        "diabetes": 9.1,
                        "obesity": 28.4,
                        "mhlth": 14.7,
                        "lpa": 22.3,
                        "csmoking": 15.1,
                        "binge": 18.6,
                        "sleep": 35.2,
                    },
                    "sdoh_index": 0.41,
                }
            ]
        },
    }


class ContextResponse(BaseModel):
    """Primary response for a geographic health context lookup."""

    location: LocationModel = Field(
        ..., description="Geocoded coordinates and matched address"
    )
    tract: TractDataModel | None = Field(
        None, description="Census tract profile for the location"
    )
    narrative: str | None = Field(
        None,
        description=(
            "AI-generated narrative summary of the tract data "
            "(only when narrative=true)"
        ),
    )
    data: TractDataModel | None = Field(
        None,
        description="Alias for tract (deprecated, use 'tract' instead)",
    )


# ---------------------------------------------------------------------------
# /v1/batch
# ---------------------------------------------------------------------------


class BatchResultLocation(BaseModel):
    """Geocoded location for a single batch result."""

    lat: float = Field(..., description="Latitude of the matched location")
    lng: float = Field(..., description="Longitude of the matched location")
    matched_address: str = Field(
        ..., description="Address string as matched by the geocoder"
    )


class BatchResultItem(BaseModel):
    """Result for a single address in a batch request."""

    address: str = Field(
        ..., description="Original input address"
    )
    status: str = Field(
        ..., description="Result status: 'ok' or 'error'"
    )
    location: BatchResultLocation | None = Field(
        None, description="Geocoded location (null on error)"
    )
    tract: TractDataModel | None = Field(
        None, description="Census tract data (null on error)"
    )
    error: str | None = Field(
        None, description="Error message (null on success)"
    )


class BatchResponse(BaseModel):
    """Aggregated results for a batch address lookup."""

    total: int = Field(..., description="Total number of addresses submitted")
    succeeded: int = Field(
        ..., description="Number of addresses successfully resolved"
    )
    failed: int = Field(
        ..., description="Number of addresses that failed"
    )
    results: list[BatchResultItem] = Field(
        ..., description="Per-address results in submission order"
    )


# ---------------------------------------------------------------------------
# /v1/nearby
# ---------------------------------------------------------------------------


class NearbyCenter(BaseModel):
    """Center point used for the nearby search."""

    lat: float = Field(..., description="Latitude of the center point")
    lng: float = Field(..., description="Longitude of the center point")


class NearbyTract(BaseModel):
    """Census tract within the search radius, with distance."""

    geoid: str = Field(
        ..., description="11-digit census tract GEOID"
    )
    name: str | None = Field(
        None, description="Human-readable tract name"
    )
    distance_miles: float = Field(
        ..., description="Distance from center point in miles"
    )
    total_population: int | None = Field(
        None, description="ACS total population estimate"
    )
    median_household_income: float | None = Field(
        None,
        description=(
            "ACS median household income in dollars. Below $30,000 correlates "
            "with higher chronic disease rates."
        ),
    )
    poverty_rate: float | None = Field(
        None,
        description=(
            "Percentage below federal poverty level (ACS). Above 20% indicates "
            "high-poverty area."
        ),
    )
    uninsured_rate: float | None = Field(
        None,
        description=(
            "Percentage without health insurance (ACS). Above 15% suggests "
            "significant access barriers."
        ),
    )
    unemployment_rate: float | None = Field(
        None,
        description=(
            "Percentage of labor force unemployed (ACS). Above 10% indicates "
            "economic distress."
        ),
    )
    median_age: float | None = Field(
        None, description="Median age of the population (ACS)"
    )
    sdoh_index: float | None = Field(
        None,
        description=(
            "Composite SDOH index (0-1). Above 0.6 indicates high social "
            "vulnerability."
        ),
    )


class NearbyResponse(BaseModel):
    """Paginated list of census tracts within a radius."""

    center: NearbyCenter = Field(
        ..., description="Center point of the search"
    )
    radius_miles: float = Field(
        ..., description="Search radius in miles"
    )
    count: int = Field(
        ..., description="Number of tracts in this page"
    )
    total: int = Field(
        ..., description="Total tracts within the radius"
    )
    offset: int = Field(
        ..., description="Number of rows skipped"
    )
    limit: int = Field(
        ..., description="Maximum rows returned per page"
    )
    tracts: list[NearbyTract] = Field(
        ..., description="Tracts sorted by distance (nearest first)"
    )


# ---------------------------------------------------------------------------
# /v1/compare
# ---------------------------------------------------------------------------


class CompareValues(BaseModel):
    """Numeric values used in a tract comparison."""

    total_population: float | None = Field(
        None, description="Total population (or average)"
    )
    median_household_income: float | None = Field(
        None,
        description="Median household income in dollars. Below $30,000 = high risk.",
    )
    poverty_rate: float | None = Field(
        None,
        description="Poverty rate %. Above 20% = high-poverty area.",
    )
    uninsured_rate: float | None = Field(
        None,
        description="Uninsured rate %. Above 15% = significant access barriers.",
    )
    unemployment_rate: float | None = Field(
        None,
        description="Unemployment rate %. Above 10% = economic distress.",
    )
    median_age: float | None = Field(
        None, description="Median age of the population"
    )
    sdoh_index: float | None = Field(
        None,
        description="Composite SDOH index (0-1). Above 0.6 = high vulnerability.",
    )


class CompareSide(BaseModel):
    """One side (A or B) of a comparison."""

    type: str = Field(
        ...,
        description=(
            "Entity type: 'tract', 'state_average', or 'national_average'"
        ),
    )
    geoid: str | None = Field(
        None, description="Tract GEOID (null for averages)"
    )
    label: str = Field(
        ..., description="Human-readable label for this side"
    )
    values: CompareValues = Field(
        ..., description="Numeric values for this entity"
    )


class CompareDifferences(BaseModel):
    """Difference (A minus B) for each compared metric."""

    total_population: float | None = Field(
        None, description="Population difference (A - B)"
    )
    median_household_income: float | None = Field(
        None, description="Income difference (A - B)"
    )
    poverty_rate: float | None = Field(
        None, description="Poverty rate difference (A - B)"
    )
    uninsured_rate: float | None = Field(
        None, description="Uninsured rate difference (A - B)"
    )
    unemployment_rate: float | None = Field(
        None, description="Unemployment rate difference (A - B)"
    )
    median_age: float | None = Field(
        None, description="Median age difference (A - B)"
    )
    sdoh_index: float | None = Field(
        None, description="SDOH index difference (A - B)"
    )


class CompareResponse(BaseModel):
    """Side-by-side comparison of two entities with computed differences."""

    a: CompareSide = Field(..., description="First entity (the tract)")
    b: CompareSide = Field(
        ..., description="Second entity (tract or average)"
    )
    differences: CompareDifferences = Field(
        ..., description="A minus B for each metric"
    )


# ---------------------------------------------------------------------------
# /v1/stats
# ---------------------------------------------------------------------------


class StateCount(BaseModel):
    """Tract count for a single state."""

    state_fips: str = Field(..., description="2-digit state FIPS code")
    tract_count: int = Field(
        ..., description="Number of loaded census tracts"
    )


class StatsResponse(BaseModel):
    """Paginated summary of loaded data by state."""

    total_states: int = Field(
        ..., description="Total number of states with loaded data"
    )
    total_tracts: int = Field(
        ..., description="Total number of loaded census tracts across all states"
    )
    offset: int = Field(..., description="Number of state rows skipped")
    limit: int = Field(
        ..., description="Maximum state rows returned per page"
    )
    states: list[StateCount] = Field(
        ..., description="Per-state tract counts"
    )


# ---------------------------------------------------------------------------
# /v1/dictionary
# ---------------------------------------------------------------------------


class FieldDefinition(BaseModel):
    """Metadata about a single data field returned by the API."""

    name: str = Field(..., description="Field name as it appears in API responses")
    type: str = Field(..., description="Data type: float, int, str, dict")
    source: str = Field(
        ..., description="Data source: ACS, SVI, PLACES, computed, census"
    )
    category: str = Field(
        ...,
        description=(
            "Category: identity, demographics, vulnerability, "
            "health_outcomes, composite"
        ),
    )
    description: str = Field(..., description="What this field measures")
    clinical_relevance: str = Field(
        ..., description="Why this matters for clinical or public-health decisions"
    )
    unit: str | None = Field(
        None, description="Unit of measurement (%, dollars, years, 0-1 scale)"
    )
    typical_range: str | None = Field(
        None, description="Typical range of values"
    )
    example_value: float | str | None = Field(
        None, description="Example value"
    )


class DictionaryCategory(BaseModel):
    """A group of related fields."""

    category: str = Field(..., description="Category name")
    description: str = Field(..., description="What this category covers")
    source: str = Field(..., description="Primary data source for this category")
    fields: list[FieldDefinition] = Field(
        ..., description="Fields in this category"
    )


class DictionaryResponse(BaseModel):
    """Complete data dictionary with field definitions and clinical context."""

    total_fields: int = Field(..., description="Total number of defined fields")
    categories: list[DictionaryCategory] = Field(
        ..., description="Fields grouped by category"
    )
