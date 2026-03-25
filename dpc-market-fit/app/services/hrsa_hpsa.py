"""HRSA Health Professional Shortage Area (HPSA) data.

Primary: Embedded CSV from HRSA data downloads (BCD_HPSA_FCT_DET_PC.csv),
filtered to our supported states.
Fallback: Socrata API (currently decomissioned, kept for future use).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.utils.cache import hpsa_cache

logger = logging.getLogger(__name__)

# HRSA HPSA dataset on data.hrsa.gov (Socrata) — currently returning 302/errors
_HPSA_DATASET_ID = "ufpc-ankf"
_HPSA_BASE_URL = f"https://data.hrsa.gov/resource/{_HPSA_DATASET_ID}.json"

# Embedded CSV path
_SHARED_HRSA = Path(__file__).resolve().parent.parent.parent.parent.parent / "shared" / "data" / "hrsa"
_LOCAL_DATA = Path(__file__).parent.parent / "data"
_HPSA_CSV_PATH = (_SHARED_HRSA if _SHARED_HRSA.exists() else _LOCAL_DATA) / "hpsa_primary_care.csv"

# In-memory index: county_fips (5-digit) → list of HPSA rows
_HPSA_INDEX: dict[str, list[dict]] | None = None


def _load_hpsa_csv() -> dict[str, list[dict]]:
    """Load HPSA CSV into an in-memory index keyed by 5-digit county FIPS."""
    global _HPSA_INDEX
    if _HPSA_INDEX is not None:
        return _HPSA_INDEX

    index: dict[str, list[dict]] = {}

    if not _HPSA_CSV_PATH.exists():
        logger.warning("HPSA CSV not found at %s", _HPSA_CSV_PATH)
        _HPSA_INDEX = index
        return index

    with open(_HPSA_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            county_fips = row.get("common_county_fips", "").strip()
            if not county_fips:
                continue
            if county_fips not in index:
                index[county_fips] = []
            index[county_fips].append(row)

    logger.info("Loaded %d HPSA entries from CSV", sum(len(v) for v in index.values()))
    _HPSA_INDEX = index
    return index


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


def _lookup_hpsa_csv(county_fips_5: str) -> HPSAData | None:
    """Look up HPSA data from embedded CSV by 5-digit county FIPS."""
    index = _load_hpsa_csv()
    rows = index.get(county_fips_5, [])

    if not rows:
        return HPSAData(is_hpsa=False)

    # Sort by score descending, take the highest
    scored_rows = []
    for row in rows:
        score = _safe_float(row.get("hpsa_score"))
        scored_rows.append((score or 0, row))
    scored_rows.sort(key=lambda x: x[0], reverse=True)

    top_score, top_row = scored_rows[0]

    designations = []
    for _, row in scored_rows:
        designations.append({
            "name": row.get("hpsa_name", ""),
            "score": _safe_float(row.get("hpsa_score")),
            "type": row.get("designation_type", ""),
            "designation": row.get("hpsa_type_code", ""),
            "ratio": row.get("hpsa_formal_ratio", ""),
        })

    return HPSAData(
        is_hpsa=True,
        hpsa_score=_safe_float(top_row.get("hpsa_score")),
        hpsa_type=top_row.get("designation_type"),
        designation_type=top_row.get("hpsa_type_code"),
        discipline="Primary Care",
        shortage_count=_safe_float(top_row.get("hpsa_fte_short")),
        designations=designations[:10],
    )


async def fetch_hpsa_data(
    *,
    state_fips: str,
    county_fips: str,
) -> HPSAData | None:
    """Fetch HPSA designations for a county.

    Tries embedded CSV first, falls back to Socrata API.
    Returns the primary care HPSA with the highest score, or None.
    """
    county_fips_5 = f"{state_fips}{county_fips}"
    cache_key = f"hpsa:{county_fips_5}"
    cached = hpsa_cache.get(cache_key)
    if cached is not None:
        return cached

    # Try embedded CSV first
    csv_result = _lookup_hpsa_csv(county_fips_5)
    if csv_result is not None:
        hpsa_cache.set(cache_key, csv_result)
        return csv_result

    # Fallback to Socrata API (currently decomissioned, kept for future)
    try:
        params: dict[str, str] = {
            "$where": (
                f"common_county_fips_code='{county_fips_5}' "
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
        logger.exception("Failed to fetch HPSA data for county %s", county_fips_5)
        return None


def _safe_float(val: str | float | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
