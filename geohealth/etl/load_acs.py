"""Load ACS 5-Year demographic data from the Census Bureau API.

Usage:
    python -m geohealth.etl.load_acs --year 2022 --state 27
    python -m geohealth.etl.load_acs --year 2022 --state all
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd
from sqlalchemy import create_engine

from geohealth.config import settings
from geohealth.etl.utils import ALL_STATE_FIPS, census_api_get, upsert_from_dataframe

logger = logging.getLogger(__name__)

ACS_BASE = "https://api.census.gov/data/{year}"

# Detail table variables
DETAIL_VARS = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_household_income",
    "B01002_001E": "median_age",
}

# Subject table variables
SUBJECT_VARS = {
    "S1701_C03_001E": "poverty_rate",
    "S2701_C05_001E": "uninsured_rate",
    "S2301_C04_001E": "unemployment_rate",
}

CENSUS_NULL = -666666666

UPDATE_COLUMNS = [
    "total_population",
    "median_household_income",
    "poverty_rate",
    "uninsured_rate",
    "unemployment_rate",
    "median_age",
]


def _fetch_table(year: int, state_fips: str, table_path: str, variables: dict) -> pd.DataFrame:
    """Fetch one ACS table for a state, returning a DataFrame with geoid + renamed columns."""
    var_list = ",".join(variables.keys())
    url = f"{ACS_BASE.format(year=year)}/{table_path}"
    params = {
        "get": var_list,
        "for": "tract:*",
        "in": f"state:{state_fips}",
    }

    resp = census_api_get(url, params)
    rows = resp.json()

    header, *data = rows
    df = pd.DataFrame(data, columns=header)

    # Build geoid from state + county + tract
    df["geoid"] = df["state"] + df["county"] + df["tract"]

    # Rename Census variable codes to our column names
    df = df.rename(columns=variables)

    # Convert to numeric, replacing Census null sentinel with None
    for col in variables.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] == CENSUS_NULL, col] = None

    keep = ["geoid"] + list(variables.values())
    return df[keep]


def load_state(year: int, state_fips: str, engine) -> int:
    """Load ACS data for one state and upsert into tract_profiles."""
    logger.info("Fetching ACS detail tables for state %s, year %d", state_fips, year)
    detail_df = _fetch_table(year, state_fips, "acs/acs5", DETAIL_VARS)

    logger.info("Fetching ACS subject tables for state %s, year %d", state_fips, year)
    subject_df = _fetch_table(year, state_fips, "acs/acs5/subject", SUBJECT_VARS)

    # Merge on geoid
    merged = detail_df.merge(subject_df, on="geoid", how="outer")
    logger.info("Merged %d tracts for state %s", len(merged), state_fips)

    return upsert_from_dataframe(merged, engine, UPDATE_COLUMNS)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Load ACS 5-Year demographics")
    parser.add_argument("--year", type=int, default=2022, help="ACS year (default: 2022)")
    parser.add_argument("--state", type=str, default="all", help="State FIPS code or 'all'")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_engine(settings.database_url_sync)
    states = ALL_STATE_FIPS if args.state == "all" else [args.state.zfill(2)]

    total = 0
    for fips in states:
        try:
            total += load_state(args.year, fips, engine)
        except Exception:
            logger.exception("Failed to load ACS for state %s", fips)

    logger.info("Done — updated %d tracts total", total)


if __name__ == "__main__":
    main()
