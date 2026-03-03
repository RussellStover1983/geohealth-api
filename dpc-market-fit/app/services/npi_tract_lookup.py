"""Tract-level NPI provider counts from pre-computed CSV.

Loads the output of etl/load_npi_tract.py into an in-memory index
keyed by 11-digit tract FIPS. Falls back gracefully when the CSV
is not yet generated.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from app.services.npi_registry import NPIData

logger = logging.getLogger(__name__)

_NPI_TRACT_CSV_PATH = Path(__file__).parent.parent / "data" / "npi_tract_counts.csv"

# Lazy-loaded in-memory index: tract_fips → row dict
_NPI_TRACT_INDEX: dict[str, dict] | None = None


def _load_npi_tract_csv() -> dict[str, dict]:
    """Load tract-level NPI counts into memory index keyed by 11-digit tract FIPS."""
    global _NPI_TRACT_INDEX
    if _NPI_TRACT_INDEX is not None:
        return _NPI_TRACT_INDEX

    index: dict[str, dict] = {}

    if not _NPI_TRACT_CSV_PATH.exists():
        logger.info(
            "NPI tract CSV not found at %s — tract-level lookup disabled",
            _NPI_TRACT_CSV_PATH,
        )
        _NPI_TRACT_INDEX = index
        return index

    with open(_NPI_TRACT_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tract_fips = row.get("tract_fips", "").strip()
            if tract_fips and len(tract_fips) == 11:
                index[tract_fips] = row

    logger.info("Loaded %d tract-level NPI entries from CSV", len(index))
    _NPI_TRACT_INDEX = index
    return index


def lookup_tract_npi(geoid: str) -> NPIData | None:
    """Look up pre-computed NPI counts for a census tract.

    Returns NPIData with is_tract_level=True if found, None otherwise.
    The caller should set total_population from ACS data for density calcs.
    """
    index = _load_npi_tract_csv()
    row = index.get(geoid)
    if not row:
        return None

    pcp_count = round(float(row.get("pcp_count", 0)))
    fqhc = round(float(row.get("fqhc_count", 0)))
    urgent_care = round(float(row.get("urgent_care_count", 0)))
    rural_health = round(float(row.get("rural_health_clinic_count", 0)))

    return NPIData(
        pcp_count=pcp_count,
        facility_counts={
            "261QF0400X": fqhc,
            "261QU0200X": urgent_care,
            "261QR1300X": rural_health,
        },
        is_tract_level=True,
    )


def reset_index() -> None:
    """Reset the in-memory index (for testing)."""
    global _NPI_TRACT_INDEX
    _NPI_TRACT_INDEX = None
