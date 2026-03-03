"""Census ACS 5-Year Estimates — demographics, insurance, income, employment.

Primary: Census Bureau API (detail tables + subject tables).
Fallback: GeoHealth API /api/v1/context/{geoid} which has ACS data pre-loaded.

Note: Insurance data uses Subject Table S2701 (not B27010).
B27010 subcells are age-specific cross-tabs and were producing incorrect totals.
S2701 provides correct aggregate rates and counts.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.utils.cache import acs_cache

logger = logging.getLogger(__name__)

# --- Detail table variables (B-tables, fetched from acs/acs5) ---
# B01001: Age/sex — total, male/female by 5-year cohorts
# B19013: Median household income
# B23025: Employment status
# B25070: Gross rent as % of income (housing cost burden - renters)

_DETAIL_VARIABLES = {
    # Total population
    "B01001_001E": "total_population",
    # Working-age (18-64) — sum male 18-64 + female 18-64
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
    # Median household income
    "B19013_001E": "median_household_income",
    # Employment status
    "B23025_001E": "employment_universe",
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

# --- Subject table variables (S-tables, fetched from acs/acs5/subject) ---
# S2701: Health Insurance Coverage Status
_SUBJECT_VARIABLES = {
    "S2701_C01_001E": "insurance_universe",   # Total civilian noninstitutionalized
    "S2701_C04_001E": "uninsured",            # Uninsured count
    "S2701_C05_001E": "uninsured_pct",        # Uninsured percent (direct)
    "S2701_C03_001E": "insured_pct",          # Insured percent
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
        # Prefer the direct percentage from S2701
        pct = _safe_float(self.raw.get("uninsured_pct"))
        if pct is not None:
            return round(pct, 1)
        # Fallback: compute from counts
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
        # From S2701 insured_pct (private + public combined);
        # we don't have employer-specific from subject table, return insured %
        pct = _safe_float(self.raw.get("insured_pct"))
        if pct is not None:
            return round(pct, 1)
        return None

    @property
    def medicaid_rate(self) -> float | None:
        return _safe_float(self.raw.get("medicaid_pct"))

    @property
    def medicare_rate(self) -> float | None:
        return _safe_float(self.raw.get("medicare_pct"))

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


async def _fetch_census_detail(
    state: str, county: str, tract: str, client: httpx.AsyncClient
) -> dict[str, int | float | None]:
    """Fetch detail table variables (B-tables)."""
    variables = ",".join(_DETAIL_VARIABLES.keys())
    url = f"https://api.census.gov/data/{settings.acs_year}/acs/acs5"
    params: dict[str, str] = {
        "get": variables,
        "for": f"tract:{tract}",
        "in": f"state:{state} county:{county}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key

    resp = await client.get(url, params=params)
    resp.raise_for_status()
    rows = resp.json()
    if len(rows) < 2:
        return {}

    header = rows[0]
    values = rows[1]
    raw = dict(zip(header, values))
    parsed: dict[str, int | float | None] = {}
    for var_code, name in _DETAIL_VARIABLES.items():
        parsed[name] = _parse_census_value(raw.get(var_code))
    return parsed


async def _fetch_census_subject(
    state: str, county: str, tract: str, client: httpx.AsyncClient
) -> dict[str, int | float | None]:
    """Fetch subject table variables (S-tables) — insurance rates."""
    variables = ",".join(_SUBJECT_VARIABLES.keys())
    url = f"https://api.census.gov/data/{settings.acs_year}/acs/acs5/subject"
    params: dict[str, str] = {
        "get": variables,
        "for": f"tract:{tract}",
        "in": f"state:{state} county:{county}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key

    resp = await client.get(url, params=params)
    resp.raise_for_status()
    rows = resp.json()
    if len(rows) < 2:
        return {}

    header = rows[0]
    values = rows[1]
    raw = dict(zip(header, values))
    parsed: dict[str, int | float | None] = {}
    for var_code, name in _SUBJECT_VARIABLES.items():
        parsed[name] = _parse_census_value(raw.get(var_code))
    return parsed


async def _fetch_acs_from_geohealth(geoid: str) -> ACSData | None:
    """Fallback: fetch ACS-equivalent data from the GeoHealth API context endpoint."""
    url = f"{settings.geohealth_api_url}/api/v1/context/{geoid}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

        data = resp.json()
        raw: dict[str, int | float | None] = {}

        raw["total_population"] = _parse_geohealth_val(data.get("total_population"))
        raw["median_household_income"] = _parse_geohealth_val(
            data.get("median_household_income")
        )

        # GeoHealth provides uninsured_rate directly (from S2701)
        uninsured_rate = data.get("uninsured_rate")
        if uninsured_rate is not None:
            raw["uninsured_pct"] = float(uninsured_rate)
            pop = raw.get("total_population")
            if pop and pop > 0:
                raw["insurance_universe"] = int(pop)
                raw["uninsured"] = int(float(uninsured_rate) / 100 * int(pop))

        unemp_rate = data.get("unemployment_rate")
        pop = raw.get("total_population")
        if unemp_rate is not None and pop and pop > 0:
            labor_force = int(int(pop) * 0.65)
            raw["civilian_labor_force"] = labor_force
            raw["unemployed"] = int(float(unemp_rate) / 100 * labor_force)
            raw["employment_universe"] = labor_force
            raw["in_labor_force"] = labor_force

        if not raw.get("total_population"):
            return None

        return ACSData(raw)

    except Exception:
        logger.exception("GeoHealth API fallback failed for ACS tract %s", geoid)
        return None


async def fetch_acs_data(geoid: str) -> ACSData | None:
    """Fetch ACS data for a single 11-digit tract GEOID.

    Makes two Census API calls (detail + subject tables), merges results.
    Falls back to GeoHealth API if Census fails.
    """
    cached = acs_cache.get(f"acs:{geoid}")
    if cached is not None:
        return cached

    state = geoid[:2]
    county = geoid[2:5]
    tract = geoid[5:]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            detail = await _fetch_census_detail(state, county, tract, client)
            subject = await _fetch_census_subject(state, county, tract, client)

        if not detail and not subject:
            logger.info(
                "No ACS data from Census for tract %s, trying GeoHealth API", geoid
            )
        else:
            # Merge detail + subject results
            parsed = {**detail, **subject}
            result = ACSData(parsed)
            acs_cache.set(f"acs:{geoid}", result)
            return result

    except Exception:
        logger.info(
            "Census ACS request failed for tract %s, trying GeoHealth API fallback",
            geoid,
        )

    # Fallback to GeoHealth API
    result = await _fetch_acs_from_geohealth(geoid)
    if result is not None:
        acs_cache.set(f"acs:{geoid}", result)
    return result


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
        if num < 0:
            return None
        if num == int(num):
            return int(num)
        return num
    except (ValueError, TypeError):
        return None


def _parse_geohealth_val(val: int | float | str | None) -> int | float | None:
    """Parse a value from GeoHealth API response."""
    if val is None:
        return None
    try:
        num = float(val)
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


async def fetch_county_population(state_fips: str, county_fips: str) -> int | None:
    """Fetch total population for a county from Census ACS."""
    cache_key = f"county_pop:{state_fips}{county_fips}"
    cached = acs_cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"https://api.census.gov/data/{settings.acs_year}/acs/acs5"
    params = {
        "get": "B01003_001E",
        "for": f"county:{county_fips}",
        "in": f"state:{state_fips}",
    }
    if settings.census_api_key:
        params["key"] = settings.census_api_key

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        rows = resp.json()
        if len(rows) >= 2:
            pop = _safe_int(_coerce_number(rows[1][0]))
            if pop and pop > 0:
                acs_cache.set(cache_key, pop)
                return pop
    except Exception:
        logger.warning("County population fetch failed for %s%s", state_fips, county_fips, exc_info=True)

    return None
