from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ProviderTier


class LocationInput(BaseModel):
    """Input location — at least one field required."""

    address: str | None = Field(None, description="Street address to geocode")
    lat: float | None = Field(None, description="Latitude", ge=-90, le=90)
    lon: float | None = Field(None, description="Longitude", ge=-180, le=180)
    zip_code: str | None = Field(
        None, description="5-digit ZIP code", pattern=r"^\d{5}$"
    )
    tract_fips: str | None = Field(
        None, description="11-digit census tract FIPS code", pattern=r"^\d{11}$"
    )


class DimensionWeights(BaseModel):
    """Override default dimension weights (must sum to 1.0)."""

    demand: float = Field(0.25, ge=0, le=1)
    supply_gap: float = Field(0.25, ge=0, le=1)
    affordability: float = Field(0.20, ge=0, le=1)
    employer: float = Field(0.20, ge=0, le=1)
    competition: float = Field(0.10, ge=0, le=1)


class MarketFitQuery(BaseModel):
    """Query parameters for /market-fit endpoint."""

    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    zip_code: str | None = None
    tract_fips: str | None = None
    radius_miles: float = Field(5.0, gt=0, le=50)
    provider_tier: ProviderTier = ProviderTier.TIER1
