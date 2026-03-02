"""Census County Business Patterns — employer landscape data.

Queries the Census Bureau CBP API for establishment counts and
employee size distributions at the county level, focusing on
industries relevant to DPC employer opportunity.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.utils.cache import cbp_cache

logger = logging.getLogger(__name__)

# CBP API endpoint
_CBP_YEAR = 2021  # Latest available CBP year
_CBP_URL = f"https://api.census.gov/data/{_CBP_YEAR}/cbp"

# NAICS codes relevant to DPC employer opportunity
# Focus on industries with 10-249 employees (DPC sweet spot)
_TARGET_NAICS = {
    "23": "Construction",
    "31-33": "Manufacturing",
    "42": "Wholesale Trade",
    "44-45": "Retail Trade",
    "48-49": "Transportation & Warehousing",
    "51": "Information",
    "52": "Finance & Insurance",
    "53": "Real Estate",
    "54": "Professional, Scientific & Technical Services",
    "55": "Management of Companies",
    "56": "Administrative & Support Services",
    "61": "Educational Services",
    "62": "Health Care & Social Assistance",
    "71": "Arts, Entertainment & Recreation",
    "72": "Accommodation & Food Services",
    "81": "Other Services",
}

# Employee size classes (EMPSZES code) in CBP
# 212 = 10-19 employees, 220 = 20-49, 230 = 50-99,
# 241 = 100-249, 242 = 250-499, 251 = 500-999, 252 = 1000+
_DPC_TARGET_SIZE_CODES = ["212", "220", "230", "241"]  # 10-249 employees
_ALL_SIZE_CODE = "001"  # All establishments


class CBPData:
    """Parsed County Business Patterns data."""

    def __init__(
        self,
        *,
        total_establishments: int = 0,
        target_establishments: int = 0,
        total_employees: int = 0,
        annual_payroll: int = 0,
        industry_breakdown: dict[str, int] | None = None,
    ):
        self.total_establishments = total_establishments
        self.target_establishments = target_establishments  # 10-249 employees
        self.total_employees = total_employees
        self.annual_payroll = annual_payroll
        self.industry_breakdown = industry_breakdown or {}

    @property
    def target_establishment_pct(self) -> float | None:
        """% of establishments in the DPC target size range (10-249 employees)."""
        if self.total_establishments > 0:
            return round(self.target_establishments / self.total_establishments * 100, 1)
        return None

    @property
    def avg_annual_wage(self) -> float | None:
        """Average annual wage ($1000s)."""
        if self.total_employees > 0:
            return round(self.annual_payroll / self.total_employees, 0)
        return None


async def fetch_cbp_data(
    *,
    state_fips: str,
    county_fips: str,
) -> CBPData | None:
    """Fetch County Business Patterns data for a county.

    Returns establishment counts, employee counts, and payroll data
    for all industries and the DPC-target size range (10-249 employees).
    """
    cache_key = f"cbp:{state_fips}{county_fips}"
    cached = cbp_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        # Fetch total establishments + employees for the county
        params: dict[str, str] = {
            "get": "ESTAB,EMP,PAYANN",
            "for": f"county:{county_fips}",
            "in": f"state:{state_fips}",
            "NAICS2017": "00",  # All NAICS
            "EMPSZES": _ALL_SIZE_CODE,
        }
        if settings.census_api_key:
            params["key"] = settings.census_api_key

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(_CBP_URL, params=params)
            resp.raise_for_status()

        rows = resp.json()
        total_estab = 0
        total_emp = 0
        total_payroll = 0

        if len(rows) >= 2:
            header = rows[0]
            values = rows[1]
            data_row = dict(zip(header, values))
            total_estab = _safe_int(data_row.get("ESTAB", 0))
            total_emp = _safe_int(data_row.get("EMP", 0))
            # PAYANN is in $1,000 units — convert to actual dollars
            total_payroll = _safe_int(data_row.get("PAYANN", 0)) * 1000

        # Fetch DPC-target size establishments (10-249 employees)
        target_estab = 0
        async with httpx.AsyncClient(timeout=20) as client:
            for size_code in _DPC_TARGET_SIZE_CODES:
                params_size = {
                    "get": "ESTAB",
                    "for": f"county:{county_fips}",
                    "in": f"state:{state_fips}",
                    "NAICS2017": "00",
                    "EMPSZES": size_code,
                }
                if settings.census_api_key:
                    params_size["key"] = settings.census_api_key

                resp = await client.get(_CBP_URL, params=params_size)
                if resp.status_code == 200:
                    size_rows = resp.json()
                    if len(size_rows) >= 2:
                        header = size_rows[0]
                        vals = size_rows[1]
                        row_data = dict(zip(header, vals))
                        target_estab += _safe_int(row_data.get("ESTAB", 0))

        # Fetch industry breakdown for context
        industry_breakdown: dict[str, int] = {}
        async with httpx.AsyncClient(timeout=20) as client:
            for naics_code, naics_label in list(_TARGET_NAICS.items())[:8]:
                params_ind = {
                    "get": "ESTAB",
                    "for": f"county:{county_fips}",
                    "in": f"state:{state_fips}",
                    "NAICS2017": naics_code,
                    "EMPSZES": _ALL_SIZE_CODE,
                }
                if settings.census_api_key:
                    params_ind["key"] = settings.census_api_key

                resp = await client.get(_CBP_URL, params=params_ind)
                if resp.status_code == 200:
                    ind_rows = resp.json()
                    if len(ind_rows) >= 2:
                        header = ind_rows[0]
                        vals = ind_rows[1]
                        row_data = dict(zip(header, vals))
                        industry_breakdown[naics_label] = _safe_int(
                            row_data.get("ESTAB", 0)
                        )

        result = CBPData(
            total_establishments=total_estab,
            target_establishments=target_estab,
            total_employees=total_emp,
            annual_payroll=total_payroll,
            industry_breakdown=industry_breakdown,
        )
        cbp_cache.set(cache_key, result)
        return result

    except Exception:
        logger.exception(
            "Failed to fetch CBP data for county %s%s", state_fips, county_fips
        )
        return None


def _safe_int(val: str | int | None) -> int:
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
