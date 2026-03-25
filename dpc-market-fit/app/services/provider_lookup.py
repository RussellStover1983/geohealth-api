"""Individual provider lookup from pre-computed per-state CSVs.

Loads providers_XX.csv files (output of etl/load_npi_tract.py) into
an in-memory index keyed by 11-digit tract FIPS. Each state is loaded
lazily on first access.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_SHARED_DERIVED = Path(__file__).resolve().parent.parent.parent.parent.parent / "shared" / "data" / "nppes" / "derived"
_LOCAL_DATA = Path(__file__).parent.parent / "data"
_DATA_DIR = _SHARED_DERIVED if _SHARED_DERIVED.exists() else _LOCAL_DATA

# State FIPS -> 2-letter abbreviation
_STATE_FIPS_TO_ABBR: dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


@dataclass
class ProviderRecord:
    """Individual provider with practice location for map plotting."""

    npi: str
    name: str
    credential: str
    taxonomy_code: str
    provider_type: str
    address: str
    city: str
    state: str
    zip_code: str
    lat: float
    lon: float
    tract_fips: str


# Lazy-loaded per-state indexes: state_fips -> {tract_fips -> [ProviderRecord, ...]}
_STATE_INDEXES: dict[str, dict[str, list[ProviderRecord]]] = {}
_LOADED_STATES: set[str] = set()


def _load_state_providers(state_fips: str) -> dict[str, list[ProviderRecord]]:
    """Load a single state's provider CSV into the index."""
    if state_fips in _LOADED_STATES:
        return _STATE_INDEXES.get(state_fips, {})

    abbr = _STATE_FIPS_TO_ABBR.get(state_fips, state_fips)
    csv_path = _DATA_DIR / f"providers_{abbr}.csv"

    index: dict[str, list[ProviderRecord]] = defaultdict(list)

    if not csv_path.exists():
        logger.info(
            "Provider CSV not found at %s -- state %s provider lookup disabled",
            csv_path, abbr,
        )
        _LOADED_STATES.add(state_fips)
        _STATE_INDEXES[state_fips] = dict(index)
        return _STATE_INDEXES[state_fips]

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            tract = row.get("tract_fips", "").strip()
            if not tract or len(tract) != 11:
                continue
            try:
                lat = float(row.get("lat", 0))
                lon = float(row.get("lon", 0))
            except (ValueError, TypeError):
                lat, lon = 0.0, 0.0

            record = ProviderRecord(
                npi=row.get("npi", "").strip(),
                name=row.get("name", "").strip(),
                credential=row.get("credential", "").strip(),
                taxonomy_code=row.get("taxonomy_code", "").strip(),
                provider_type=row.get("provider_type", "PCP").strip(),
                address=row.get("address", "").strip(),
                city=row.get("city", "").strip(),
                state=row.get("state", "").strip(),
                zip_code=row.get("zip", "").strip(),
                lat=lat,
                lon=lon,
                tract_fips=tract,
            )
            index[tract].append(record)
            count += 1

    logger.info("Loaded %d providers for state %s from CSV", count, abbr)
    _LOADED_STATES.add(state_fips)
    _STATE_INDEXES[state_fips] = dict(index)
    return _STATE_INDEXES[state_fips]


def lookup_providers(
    tract_fips: str,
    *,
    provider_type: str | None = None,
) -> list[ProviderRecord]:
    """Return individual providers assigned to a tract.

    Args:
        tract_fips: 11-digit census tract FIPS code.
        provider_type: Optional filter (PCP, FQHC, URGENT_CARE, etc.)

    Returns:
        List of ProviderRecord instances for the tract.
    """
    if len(tract_fips) < 2:
        return []

    state_fips = tract_fips[:2]
    index = _load_state_providers(state_fips)
    providers = index.get(tract_fips, [])

    if provider_type:
        providers = [p for p in providers if p.provider_type == provider_type]

    return providers


def reset_index() -> None:
    """Reset all in-memory indexes (for testing)."""
    global _STATE_INDEXES, _LOADED_STATES
    _STATE_INDEXES = {}
    _LOADED_STATES = set()
