"""Census ACS 5-Year Estimates — demographics, insurance, income, employment.

Fetches tract-level data from the Census Bureau API for the tables
needed by the DPC Market Fit scoring engine.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.utils.cache import acs_cache

logger = logging.getLogger(__name__)

# ACS table variable mappings
# B01001: Age/sex — total, male/female by 5-year cohorts
# B27001: Health insurance by age — uninsured counts
# B27010: Insurance type — employer, Medicaid, Medicare, uninsured
# B19013: Median household income
# B23025: Employment status
# B25070: Gross rent as % of income (housing cost burden - renters)

_VARIABLES = {
    # Total population
    "B01001_001E": "total_population",
    # Working-age (18-64) — sum male 18-64 + female 18-64
    # Male 18-19 through 60-64
    "B01001_007E": "male_18_19",
    "B01001_008E": "male_20",
    "B01001_009E": "male_21",
    "B01001_010E": "male_22_24",
    "B01001_011E": "male_25_29",
    "B01001_012E": "male_30_34",
    "B01001_013E": "male_35_39",
    "B01001_014E": "male_40_44",
    "B01001_015E": "male_45_49",
    "B01001_016E": "male_50_54",
    "B01001_017E": "male_55_59",
    "B01001_018E": "male_60_61",
    "B01001_019E": "male_62_64",
    # Female 18-19 through 60-64
    "B01001_031E": "female_18_19",
    "B01001_032E": "female_20",
    "B01001_033E": "female_21",
    "B01001_034E": "female_22_24",
    "B01001_035E": "female_25_29",
    "B01001_036E": "female_30_34",
    "B01001_037E": "female_35_39",
    "B01001_038E": "female_40_44",
    "B01001_039E": "female_45_49",
    "B01001_040E": "female_50_54",
    "B01001_041E": "female_55_59",
    "B01001_042E": "female_60_61",
    "B01001_043E": "female_62_64",
    # Insurance by type (B27010)
    "B27010_001E": "insurance_universe",  # Civilian non-institutionalized
    "B27010_017E": "employer_insurance",   # With employer-based
    "B27010_033E": "medicaid",             # With Medicaid/means-tested
    "B27010_050E": "medicare",             # With Medicare
    "B27010_066E": "uninsured",            # No insurance
    # Median household income
    "B19013_001E": "median_household_income",
    # Employment status
    "B23025_001E": "employment_universe",  # Pop 16+
    "B23025_003E": "civilian_labor_force",
    "B23025_005E": "unemployed",
    "B23025_002E": "in_labor_force",
    # Housing cost burden — renters paying 30%+ of income
    "B25070_001E": "renters_total",
    "B25070_007E": "renters_30_34pct",
    "B25070_008E": "renters_35_39pct",
    "B25070_009E": "renters_40_49pct",
    "B25070_010E": "renters_50pct_plus",
}

# Working-age variable keys (18-64)
_WORKING_AGE_KEYS = [
    "male_18_19", "male_20", "male_21", "male_22_24",
    "male_25_29", "male_30_34", "male_35_39", "male_40_44",
    "male_45_49", "male_50_54", "male_55_59", "male_60_61", "male_62_64",
    "female_18_19", "female_20", "female_21", "female_22_24",
    "female_25_29", "female_30_34", "female_35_39", "female_40_44",
    "female_45_49", "female_50_54", "female_55_59", "female_60_61", "female_62_64",
]


class ACSData:
    """Parsed ACS data for a single tract."""

    def __init__(self, raw: dict[str, int | float | None]):
        self.raw = raw

    @property
    def total_population(self) -> int | None:
        return _safe_int(self.raw.get("total_population"))

    @property
    def working_age_population(self) -> int | None:
        vals = [self.raw.get(k) for k in _WORKING_AGE_KEYS]
        if all(v is None for v in vals):
            return None
        return sum(v for v in vals if v is not None and v >= 0)

    @property
    def median_household_income(self) -> float | None:
        return _safe_float(self.raw.get("median_household_income"))

    @property
    def uninsured_rate(self) -> float | None:
        universe = _safe_int(self.raw.get("insurance_universe"))
        uninsured = _safe_int(self.raw.get("uninsured"))
        if universe and universe > 0 and uninsured is not None:
            return round(uninsured / universe * 100, 1)
        return None

    @property
    def uninsured_count(self) -> int | None:
        return _safe_int(self.raw.get("uninsured"))

    @property
    def employer_insured_rate(self) -> float | None:
        universe = _safe_int(self.raw.get("insurance_universe"))
        employer = _safe_int(self.raw.get("employer_insurance"))
        if universe and universe > 0 and employer is not None:
            return round(employer / universe * 100, 1)
        return None

    @property
    def medicaid_rate(self) -> float | None:
        universe = _safe_int(self.raw.get("insurance_universe"))
        medicaid = _safe_int(self.raw.get("medicaid"))
        if universe and universe > 0 and medicaid is not None:
            return round(medicaid / universe * 100, 1)
        return None

    @property
    def medicare_rate(self) -> float | None:
        universe = _safe_int(self.raw.get("insurance_universe"))
        medicare = _safe_int(self.raw.get("medicare"))
        if universe and universe > 0 and medicare is not None:
            return round(medicare / universe * 100, 1)
        return None

    @property
    def unemployment_rate(self) -> float | None:
        labor = _safe_int(self.raw.get("civilian_labor_force"))
        unemployed = _safe_int(self.raw.get("unemployed"))
        if labor and labor > 0 and unemployed is not None:
            return round(unemployed / labor * 100, 1)
        return None

    @property
    def employment_rate(self) -> float | None:
        rate = self.unemployment_rate
        if rate is not None:
            return round(100.0 - rate, 1)
        return None

    @property
    def housing_cost_burden_rate(self) -> float | None:
        """% of renters paying 30%+ of income on housing."""
        total = _safe_int(self.raw.get("renters_total"))
        if not total or total <= 0:
            return None
        burdened = sum(
            _safe_int(self.raw.get(k)) or 0
            for k in ["renters_30_34pct", "renters_35_39pct",
                       "renters_40_49pct", "renters_50pct_plus"]
        )
        return round(burdened / total * 100, 1)

    @property
    def dpc_as_pct_of_income(self) -> float | None:
        """$100/mo DPC membership as % of annual median household income."""
        income = self.median_household_income
        if income and income > 0:
            return round((1200 / income) * 100, 2)
        return None


async def fetch_acs_data(geoid: str) -> ACSData | None:
    """Fetch ACS data for a single 11-digit tract GEOID.

    Returns None if the Census API is unreachable or returns no data.
    """
    cached = acs_cache.get(f"acs:{geoid}")
    if cached is not None:
        return cached

    state = geoid[:2]
    county = geoid[2:5]
    tract = geoid[5:]

    variables = ",".join(_VARIABLES.keys())
    url = f"https://api.census.gov/data/{settings.acs_year}/acs/acs5"
    params: dict[str, str] = {
        "get": variables,
        "for": f"tract:{tract}",
        "in": f"state:{state} county:{county}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

        rows = resp.json()
        if len(rows) < 2:
            logger.warning("No ACS data returned for tract %s", geoid)
            return None

        header = rows[0]
        values = rows[1]
        raw_census = dict(zip(header, values))

        # Map Census variable names to our friendly names
        parsed: dict[str, int | float | None] = {}
        for var_code, friendly_name in _VARIABLES.items():
            val = raw_census.get(var_code)
            parsed[friendly_name] = _parse_census_value(val)

        result = ACSData(parsed)
        acs_cache.set(f"acs:{geoid}", result)
        return result

    except Exception:
        logger.exception("Failed to fetch ACS data for tract %s", geoid)
        return None


async def fetch_acs_multi(geoids: list[str]) -> dict[str, ACSData | None]:
    """Fetch ACS data for multiple tracts. Returns dict keyed by GEOID."""
    results: dict[str, ACSData | None] = {}
    for geoid in geoids:
        results[geoid] = await fetch_acs_data(geoid)
    return results


def _parse_census_value(val: str | int | float | None) -> int | float | None:
    """Parse a Census API value, handling nulls and negative sentinel values."""
    if val is None:
        return None
    try:
        num = float(val)
        # Census uses negative values as error codes
        if num < 0:
            return None
        if num == int(num):
            return int(num)
        return num
    except (ValueError, TypeError):
        return None


def _safe_int(val: int | float | None) -> int | None:
    if val is None:
        return None
    return int(val)


def _safe_float(val: int | float | None) -> float | None:
    if val is None:
        return None
    return float(val)
