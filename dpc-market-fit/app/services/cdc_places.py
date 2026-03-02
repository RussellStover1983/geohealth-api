"""CDC PLACES — chronic disease prevalence at the census tract level.

Uses the Socrata Open Data API to fetch model-based health outcome
estimates from the BRFSS.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.utils.cache import places_cache

logger = logging.getLogger(__name__)

# CDC PLACES measures relevant to DPC demand
_MEASURES = [
    "DIABETES",   # Diagnosed diabetes
    "BPHIGH",     # High blood pressure
    "OBESITY",    # Obesity
    "COPD",       # Chronic obstructive pulmonary disease
    "DEPRESSION", # Depression
    "CASTHMA",    # Current asthma
    "ACCESS2",    # No health insurance (18-64)
    "CHECKUP",    # Annual checkup
]

# Map PLACES measure IDs to our field names
_MEASURE_MAP = {
    "DIABETES": "diabetes_pct",
    "BPHIGH": "hypertension_pct",
    "OBESITY": "obesity_pct",
    "COPD": "copd_pct",
    "DEPRESSION": "depression_pct",
    "CASTHMA": "asthma_pct",
    "ACCESS2": "no_insurance_pct",
    "CHECKUP": "annual_checkup_pct",
}


class PLACESData:
    """Parsed CDC PLACES data for a single tract."""

    def __init__(self, measures: dict[str, float | None]):
        self.measures = measures

    @property
    def diabetes_pct(self) -> float | None:
        return self.measures.get("diabetes_pct")

    @property
    def hypertension_pct(self) -> float | None:
        return self.measures.get("hypertension_pct")

    @property
    def obesity_pct(self) -> float | None:
        return self.measures.get("obesity_pct")

    @property
    def copd_pct(self) -> float | None:
        return self.measures.get("copd_pct")

    @property
    def depression_pct(self) -> float | None:
        return self.measures.get("depression_pct")

    @property
    def asthma_pct(self) -> float | None:
        return self.measures.get("asthma_pct")

    @property
    def chronic_disease_burden(self) -> float | None:
        """Composite chronic disease burden — average of available measures."""
        vals = [
            self.diabetes_pct, self.hypertension_pct, self.obesity_pct,
            self.copd_pct, self.depression_pct, self.asthma_pct,
        ]
        available = [v for v in vals if v is not None]
        if not available:
            return None
        return round(sum(available) / len(available), 1)


async def fetch_places_data(geoid: str) -> PLACESData | None:
    """Fetch CDC PLACES data for a tract GEOID.

    Returns None if the API is unreachable or returns no data.
    """
    cached = places_cache.get(f"places:{geoid}")
    if cached is not None:
        return cached

    # Socrata expects LocationID as the 11-digit tract FIPS
    url = f"https://data.cdc.gov/resource/{settings.cdc_places_dataset_id}.json"
    measures_filter = ",".join(f"'{m}'" for m in _MEASURES)
    params: dict[str, str] = {
        "$where": f"locationid='{geoid}' AND measure IN({measures_filter})",
        "$select": "measure,data_value",
        "$limit": "50",
    }
    if settings.socrata_app_token:
        params["$$app_token"] = settings.socrata_app_token

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

        rows = resp.json()
        measures: dict[str, float | None] = {}
        for row in rows:
            measure_id = row.get("measure", "").upper()
            friendly = _MEASURE_MAP.get(measure_id)
            if friendly:
                try:
                    measures[friendly] = float(row["data_value"])
                except (ValueError, TypeError, KeyError):
                    measures[friendly] = None

        result = PLACESData(measures)
        places_cache.set(f"places:{geoid}", result)
        return result

    except Exception:
        logger.exception("Failed to fetch PLACES data for tract %s", geoid)
        return None


async def fetch_places_multi(geoids: list[str]) -> dict[str, PLACESData | None]:
    """Fetch PLACES data for multiple tracts."""
    results: dict[str, PLACESData | None] = {}
    for geoid in geoids:
        results[geoid] = await fetch_places_data(geoid)
    return results
