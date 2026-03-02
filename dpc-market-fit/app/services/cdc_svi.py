"""CDC/ATSDR Social Vulnerability Index — tract-level vulnerability themes.

Uses the Socrata Open Data API to fetch SVI percentile rankings.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.utils.cache import svi_cache

logger = logging.getLogger(__name__)

# SVI theme fields
_SVI_FIELDS = [
    "rpl_theme1",  # Socioeconomic status
    "rpl_theme2",  # Household characteristics & disability
    "rpl_theme3",  # Racial & ethnic minority status
    "rpl_theme4",  # Housing type & transportation
    "rpl_themes",  # Overall composite
]


class SVIData:
    """Parsed CDC/ATSDR SVI data for a single tract."""

    def __init__(self, themes: dict[str, float | None]):
        self.themes = themes

    @property
    def socioeconomic(self) -> float | None:
        """RPL_THEME1: Socioeconomic status percentile (0-1)."""
        return self.themes.get("rpl_theme1")

    @property
    def household_disability(self) -> float | None:
        """RPL_THEME2: Household characteristics & disability (0-1)."""
        return self.themes.get("rpl_theme2")

    @property
    def minority_language(self) -> float | None:
        """RPL_THEME3: Racial & ethnic minority status (0-1)."""
        return self.themes.get("rpl_theme3")

    @property
    def housing_transportation(self) -> float | None:
        """RPL_THEME4: Housing type & transportation (0-1)."""
        return self.themes.get("rpl_theme4")

    @property
    def composite(self) -> float | None:
        """RPL_THEMES: Overall SVI composite percentile (0-1)."""
        return self.themes.get("rpl_themes")


async def fetch_svi_data(geoid: str) -> SVIData | None:
    """Fetch SVI data for a tract GEOID.

    Returns None if the API is unreachable or returns no data.
    """
    cached = svi_cache.get(f"svi:{geoid}")
    if cached is not None:
        return cached

    url = f"https://data.cdc.gov/resource/{settings.cdc_svi_dataset_id}.json"
    fields = ",".join(_SVI_FIELDS)
    params: dict[str, str] = {
        "$where": f"fips='{geoid}'",
        "$select": f"fips,{fields}",
        "$limit": "1",
    }
    if settings.socrata_app_token:
        params["$$app_token"] = settings.socrata_app_token

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

        rows = resp.json()
        if not rows:
            logger.warning("No SVI data for tract %s", geoid)
            return None

        row = rows[0]
        themes: dict[str, float | None] = {}
        for field in _SVI_FIELDS:
            val = row.get(field)
            if val is not None:
                try:
                    parsed = float(val)
                    # SVI uses -999 as a sentinel for missing data
                    themes[field] = parsed if parsed >= 0 else None
                except (ValueError, TypeError):
                    themes[field] = None
            else:
                themes[field] = None

        result = SVIData(themes)
        svi_cache.set(f"svi:{geoid}", result)
        return result

    except Exception:
        logger.exception("Failed to fetch SVI data for tract %s", geoid)
        return None


async def fetch_svi_multi(geoids: list[str]) -> dict[str, SVIData | None]:
    """Fetch SVI data for multiple tracts."""
    results: dict[str, SVIData | None] = {}
    for geoid in geoids:
        results[geoid] = await fetch_svi_data(geoid)
    return results
