"""HRSA Health Professional Shortage Area (HPSA) data.

Queries the HRSA Data Warehouse via Socrata API for HPSA designations
and shortage scores at the county/service area level.
"""

from __future__ import annotations

import logging

import httpx

from app.utils.cache import hpsa_cache

logger = logging.getLogger(__name__)

# HRSA HPSA dataset on data.hrsa.gov (Socrata)
_HPSA_DATASET_ID = "ufpc-ankf"
_HPSA_BASE_URL = f"https://data.hrsa.gov/resource/{_HPSA_DATASET_ID}.json"


class HPSAData:
    """Parsed HPSA data for a geographic area."""

    def __init__(
        self,
        *,
        is_hpsa: bool = False,
        hpsa_score: float | None = None,
        hpsa_type: str | None = None,
        designation_type: str | None = None,
        discipline: str | None = None,
        shortage_count: float | None = None,
        designations: list[dict] | None = None,
    ):
        self.is_hpsa = is_hpsa
        self.hpsa_score = hpsa_score
        self.hpsa_type = hpsa_type
        self.designation_type = designation_type
        self.discipline = discipline
        self.shortage_count = shortage_count
        self.designations = designations or []


async def fetch_hpsa_data(
    *,
    state_fips: str,
    county_fips: str,
) -> HPSAData | None:
    """Fetch HPSA designations for a county.

    Returns the primary care HPSA with the highest score, or None.
    """
    cache_key = f"hpsa:{state_fips}{county_fips}"
    cached = hpsa_cache.get(cache_key)
    if cached is not None:
        return cached

    fips_county = f"{state_fips}{county_fips}"

    try:
        params: dict[str, str] = {
            "$where": (
                f"common_county_fips_code='{fips_county}' "
                "AND hpsa_discipline_class='Primary Care'"
            ),
            "$select": (
                "hpsa_name,hpsa_score,hpsa_type_description,"
                "hpsa_shortage_designation_type,hpsa_formal_ratio,"
                "hpsa_discipline_class,hpsa_provider_ratio_to_population"
            ),
            "$limit": "20",
            "$order": "hpsa_score DESC",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(_HPSA_BASE_URL, params=params)
            resp.raise_for_status()

        rows = resp.json()
        if not rows:
            result = HPSAData(is_hpsa=False)
            hpsa_cache.set(cache_key, result)
            return result

        # Take the highest-scoring designation
        top = rows[0]
        score = _safe_float(top.get("hpsa_score"))

        designations = []
        for row in rows:
            designations.append({
                "name": row.get("hpsa_name", ""),
                "score": _safe_float(row.get("hpsa_score")),
                "type": row.get("hpsa_type_description", ""),
                "designation": row.get("hpsa_shortage_designation_type", ""),
                "ratio": row.get("hpsa_formal_ratio", ""),
            })

        result = HPSAData(
            is_hpsa=True,
            hpsa_score=score,
            hpsa_type=top.get("hpsa_type_description"),
            designation_type=top.get("hpsa_shortage_designation_type"),
            discipline="Primary Care",
            designations=designations,
        )
        hpsa_cache.set(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to fetch HPSA data for county %s", fips_county)
        return None


def _safe_float(val: str | float | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
