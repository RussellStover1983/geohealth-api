"""CDC PLACES — chronic disease prevalence at the census tract level.

Primary: Socrata Open Data API (dataset cwsq-ngmh).
Fallback: GeoHealth API /api/v1/context/{geoid} which has PLACES data pre-loaded.
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

# Map GeoHealth API places_measures keys to our field names
_GEOHEALTH_MAP = {
    "diabetes": "diabetes_pct",
    "bphigh": "hypertension_pct",
    "obesity": "obesity_pct",
    "copd": "copd_pct",
    "depression": "depression_pct",
    "casthma": "asthma_pct",
    "access2": "no_insurance_pct",
    "checkup": "annual_checkup_pct",
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


async def _fetch_places_from_geohealth(geoid: str) -> PLACESData | None:
    """Fallback: fetch PLACES data from the GeoHealth API context endpoint."""
    url = f"{settings.geohealth_api_url}/api/v1/context/{geoid}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

        data = resp.json()
        places_measures = data.get("places_measures")
        if not places_measures or not isinstance(places_measures, dict):
            return None

        measures: dict[str, float | None] = {}
        for gh_key, our_key in _GEOHEALTH_MAP.items():
            val = places_measures.get(gh_key)
            if val is not None:
                try:
                    measures[our_key] = float(val)
                except (ValueError, TypeError):
                    measures[our_key] = None

        if not measures:
            return None

        return PLACESData(measures)

    except Exception:
        logger.exception("GeoHealth API fallback failed for PLACES tract %s", geoid)
        return None


async def fetch_places_data(geoid: str) -> PLACESData | None:
    """Fetch CDC PLACES data for a tract GEOID.

    Tries Socrata first, falls back to GeoHealth API.
    Returns None if both are unreachable or return no data.
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
        if rows and isinstance(rows, list) and len(rows) > 0:
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

        # Socrata returned empty — fall through to GeoHealth fallback
        logger.info(
            "No PLACES data from Socrata for tract %s, trying GeoHealth API", geoid
        )

    except Exception:
        logger.info(
            "Socrata PLACES request failed for tract %s, trying GeoHealth API fallback",
            geoid,
        )

    # Fallback to GeoHealth API
    result = await _fetch_places_from_geohealth(geoid)
    if result is not None:
        places_cache.set(f"places:{geoid}", result)
    return result


async def fetch_places_multi(geoids: list[str]) -> dict[str, PLACESData | None]:
    """Fetch PLACES data for multiple tracts."""
    results: dict[str, PLACESData | None] = {}
    for geoid in geoids:
        results[geoid] = await fetch_places_data(geoid)
    return results
