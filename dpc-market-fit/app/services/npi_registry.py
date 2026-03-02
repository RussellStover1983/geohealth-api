"""NPPES NPI Registry — provider supply data via CMS public API.

Queries the NPI Registry API to count primary care providers near a location,
using taxonomy codes from npi_taxonomy_config.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from app.config import settings
from app.utils.cache import npi_cache

logger = logging.getLogger(__name__)

_TAXONOMY_CONFIG: dict | None = None

_NPI_API_URL = "https://npiregistry.cms.hhs.gov/api/"


def _load_taxonomy_config() -> dict:
    global _TAXONOMY_CONFIG
    if _TAXONOMY_CONFIG is None:
        config_path = Path(__file__).parent.parent / "data" / "npi_taxonomy_config.json"
        with open(config_path) as f:
            _TAXONOMY_CONFIG = json.load(f)
    return _TAXONOMY_CONFIG


def get_taxonomy_codes(tier: str = "tier1") -> list[str]:
    """Return flat list of taxonomy codes for the given tier."""
    config = _load_taxonomy_config()
    codes: list[str] = []

    if tier in ("tier1", "tier1_tier2", "all"):
        tier1 = config["tiers"]["tier1"]["codes"]
        for group in tier1.values():
            codes.extend(item["code"] for item in group)

    if tier in ("tier1_tier2", "all"):
        tier2 = config["tiers"]["tier2"]["codes"]
        for group in tier2.values():
            codes.extend(item["code"] for item in group)

    return codes


def get_facility_codes() -> list[str]:
    """Return facility-level NPI taxonomy codes (FQHCs, urgent care, etc.)."""
    config = _load_taxonomy_config()
    return [item["code"] for item in config["facility_codes"]["codes"]]


class NPIData:
    """Parsed NPI provider data for a geographic area."""

    def __init__(
        self,
        *,
        pcp_count: int = 0,
        pcp_details: list[dict] | None = None,
        facility_counts: dict[str, int] | None = None,
        total_population: int | None = None,
    ):
        self.pcp_count = pcp_count
        self.pcp_details = pcp_details or []
        self.facility_counts = facility_counts or {}
        self.total_population = total_population

    @property
    def pcp_per_100k(self) -> float | None:
        """Primary care providers per 100,000 population."""
        if self.total_population and self.total_population > 0:
            return round(self.pcp_count / self.total_population * 100_000, 1)
        return None

    @property
    def fqhc_count(self) -> int:
        return self.facility_counts.get("261QF0400X", 0)

    @property
    def urgent_care_count(self) -> int:
        return self.facility_counts.get("261QU0200X", 0)

    @property
    def rural_health_clinic_count(self) -> int:
        return self.facility_counts.get("261QR1300X", 0)


async def fetch_npi_providers(
    *,
    state: str,
    city: str | None = None,
    postal_code: str | None = None,
    tier: str = "tier1",
) -> NPIData | None:
    """Query NPPES API for PCP counts in a geographic area.

    The NPPES API doesn't support radius queries, so we search by
    state + city or postal_code and aggregate results.
    """
    cache_key = f"npi:{state}:{city or ''}:{postal_code or ''}:{tier}"
    cached = npi_cache.get(cache_key)
    if cached is not None:
        return cached

    taxonomy_codes = get_taxonomy_codes(tier)
    pcp_count = 0
    pcp_details: list[dict] = []

    # NPPES API supports one taxonomy_description per call, so we query by
    # enumeration_type and filter results. We batch by searching the state/area.
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Search for individual providers (NPI-1)
            for taxonomy_code in taxonomy_codes[:16]:  # Limit API calls
                params: dict[str, str] = {
                    "version": "2.1",
                    "enumeration_type": "NPI-1",
                    "taxonomy_description": taxonomy_code,
                    "state": state,
                    "limit": "200",
                }
                if postal_code:
                    params["postal_code"] = postal_code[:5]
                elif city:
                    params["city"] = city

                resp = await client.get(_NPI_API_URL, params=params)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                result_count = data.get("result_count", 0)
                pcp_count += result_count

                # Collect first few provider details
                for result in data.get("results", [])[:5]:
                    basic = result.get("basic", {})
                    pcp_details.append({
                        "npi": result.get("number"),
                        "name": f"{basic.get('first_name', '')} {basic.get('last_name', '')}".strip(),
                        "credential": basic.get("credential", ""),
                        "taxonomy": taxonomy_code,
                    })

        # Search for facilities
        facility_counts: dict[str, int] = {}
        facility_codes = get_facility_codes()

        async with httpx.AsyncClient(timeout=20) as client:
            for fac_code in facility_codes:
                params = {
                    "version": "2.1",
                    "enumeration_type": "NPI-2",
                    "taxonomy_description": fac_code,
                    "state": state,
                    "limit": "10",
                }
                if postal_code:
                    params["postal_code"] = postal_code[:5]
                elif city:
                    params["city"] = city

                resp = await client.get(_NPI_API_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    facility_counts[fac_code] = data.get("result_count", 0)

        result = NPIData(
            pcp_count=pcp_count,
            pcp_details=pcp_details[:20],
            facility_counts=facility_counts,
        )
        npi_cache.set(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to fetch NPI data for %s", state)
        return None
