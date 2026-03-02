from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ScoreCategory


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class ResolvedLocation(BaseModel):
    """Resolved location metadata returned with every response."""

    input: str = Field(..., description="Original location input")
    resolved_lat: float | None = Field(None, description="Resolved latitude")
    resolved_lon: float | None = Field(None, description="Resolved longitude")
    primary_tract_fips: str | None = Field(
        None, description="11-digit FIPS of the primary census tract"
    )
    tracts_in_radius: list[str] = Field(
        default_factory=list, description="Tract FIPS codes within the search radius"
    )
    radius_miles: float = Field(..., description="Search radius used")
    market_population: int | None = Field(
        None, description="Total population across all tracts in radius"
    )


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


class CompositeScore(BaseModel):
    """Weighted composite DPC Market Fit Score."""

    value: float = Field(..., description="Composite score 0-100")
    percentile: int | None = Field(
        None, description="Percentile rank vs national distribution"
    )
    category: ScoreCategory = Field(..., description="Score category")
    weights_used: dict[str, float] = Field(
        ..., description="Dimension weights applied"
    )


class DimensionScore(BaseModel):
    """Score for a single dimension."""

    score: float = Field(..., description="Dimension score 0-100")
    category: ScoreCategory = Field(..., description="Score category")
    summary: str = Field("", description="Brief summary of this dimension")
    data_completeness: float = Field(
        1.0, description="Fraction of data sources available (0-1)"
    )


# ---------------------------------------------------------------------------
# Data vintage
# ---------------------------------------------------------------------------


class DataVintage(BaseModel):
    """Tracks the vintage of each data source used."""

    census_acs: str | None = Field(None, description="ACS data year")
    cdc_places: str | None = Field(None, description="CDC PLACES release")
    cdc_svi: str | None = Field(None, description="CDC SVI year")
    npi: str | None = Field(None, description="NPI data month")
    cbp: str | None = Field(None, description="CBP data year")


# ---------------------------------------------------------------------------
# Main response
# ---------------------------------------------------------------------------


class MarketFitResponse(BaseModel):
    """Primary response from /api/v1/market-fit."""

    location: ResolvedLocation
    composite_score: CompositeScore
    dimensions: dict[str, DimensionScore] = Field(
        ..., description="Per-dimension scores"
    )
    narrative: str | None = Field(
        None, description="AI-generated market viability narrative"
    )
    data_vintage: DataVintage


# ---------------------------------------------------------------------------
# Demand detail response
# ---------------------------------------------------------------------------


class ChronicDiseasePrevalence(BaseModel):
    """Chronic disease prevalence rates from CDC PLACES."""

    diabetes_pct: float | None = None
    hypertension_pct: float | None = None
    obesity_pct: float | None = None
    copd_pct: float | None = None
    depression_pct: float | None = None
    asthma_pct: float | None = None


class DemandDetailResponse(BaseModel):
    """Detailed demand indicators for /api/v1/market-fit/demand."""

    location: ResolvedLocation
    total_population: int | None = None
    working_age_population: int | None = Field(
        None, description="Population aged 18-64"
    )
    uninsured_rate: float | None = None
    uninsured_count: int | None = None
    employer_insured_rate: float | None = Field(
        None, description="Employer-sponsored insurance rate (proxy for HDHP exposure)"
    )
    medicaid_rate: float | None = None
    medicare_rate: float | None = None
    median_household_income: float | None = None
    chronic_disease_prevalence: ChronicDiseasePrevalence | None = None
    svi_composite: float | None = Field(
        None, description="CDC/ATSDR SVI overall percentile (0-1)"
    )
    demand_score: DimensionScore | None = None
    affordability_score: DimensionScore | None = None
    data_vintage: DataVintage


# ---------------------------------------------------------------------------
# Supply detail response
# ---------------------------------------------------------------------------


class SupplyDetailResponse(BaseModel):
    """Detailed supply indicators for /api/v1/market-fit/supply."""

    location: ResolvedLocation
    pcp_count: int = Field(0, description="Primary care providers in the area")
    pcp_per_100k: float | None = Field(
        None, description="PCPs per 100,000 population"
    )
    national_benchmark_pcp_per_100k: float = Field(
        75.0, description="National benchmark for PCPs per 100k"
    )
    is_hpsa: bool = Field(False, description="Is a Health Professional Shortage Area")
    hpsa_score: float | None = Field(
        None, description="HPSA score (0-25, higher = greater shortage)"
    )
    hpsa_type: str | None = Field(None, description="HPSA designation type")
    fqhc_count: int = Field(0, description="FQHCs in the area")
    urgent_care_count: int = Field(0, description="Urgent care clinics in the area")
    rural_health_clinic_count: int = Field(0, description="Rural health clinics")
    supply_gap_score: DimensionScore | None = None
    data_vintage: DataVintage


# ---------------------------------------------------------------------------
# Employer detail response
# ---------------------------------------------------------------------------


class EmployerDetailResponse(BaseModel):
    """Detailed employer indicators for /api/v1/market-fit/employer."""

    location: ResolvedLocation
    total_establishments: int = Field(0, description="Total business establishments")
    target_establishments: int = Field(
        0, description="Establishments with 10-249 employees (DPC target)"
    )
    target_establishment_pct: float | None = Field(
        None, description="% of establishments in DPC target size range"
    )
    total_employees: int = Field(0, description="Total employees in the area")
    avg_annual_wage: float | None = Field(None, description="Average annual wage ($)")
    industry_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Establishments by industry"
    )
    employer_score: DimensionScore | None = None
    data_vintage: DataVintage


# ---------------------------------------------------------------------------
# Competition detail response
# ---------------------------------------------------------------------------


class CompetitionDetailResponse(BaseModel):
    """Detailed competition indicators for /api/v1/market-fit/competition."""

    location: ResolvedLocation
    fqhc_count: int = Field(0, description="FQHCs competing for underserved patients")
    urgent_care_count: int = Field(0, description="Urgent care clinics nearby")
    rural_health_clinic_count: int = Field(0, description="Rural health clinics nearby")
    pcp_density_per_100k: float | None = Field(
        None, description="PCP density per 100k — higher = more saturated"
    )
    competition_score: DimensionScore | None = None
    data_vintage: DataVintage


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Structured error response."""

    error: bool = Field(True, description="Always true for errors")
    status_code: int
    detail: str
