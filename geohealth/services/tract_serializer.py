"""Shared serialization helpers for TractProfile → dict conversion."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geohealth.db.models import TractProfile
    from geohealth.services.geocoder import GeocodedLocation


def tract_to_dict(tract: TractProfile) -> dict:
    """Convert a TractProfile ORM instance to a full response dict."""
    return {
        "geoid": tract.geoid,
        "state_fips": tract.state_fips,
        "county_fips": tract.county_fips,
        "tract_code": tract.tract_code,
        "name": tract.name,
        "total_population": tract.total_population,
        "median_household_income": tract.median_household_income,
        "poverty_rate": tract.poverty_rate,
        "uninsured_rate": tract.uninsured_rate,
        "unemployment_rate": tract.unemployment_rate,
        "median_age": tract.median_age,
        "svi_themes": tract.svi_themes,
        "places_measures": tract.places_measures,
        "sdoh_index": tract.sdoh_index,
        "epa_data": tract.epa_data,
    }


def fips_fallback_dict(location: GeocodedLocation) -> dict | None:
    """Build a minimal tract dict from geocoder FIPS codes, or None if missing."""
    if location.state_fips and location.county_fips and location.tract_fips:
        return {
            "geoid": f"{location.state_fips}{location.county_fips}{location.tract_fips}",
            "state_fips": location.state_fips,
            "county_fips": location.county_fips,
            "tract_code": location.tract_fips,
        }
    return None
