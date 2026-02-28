"""Load multi-year ACS data into the trends JSONB column.

Fetches ACS 5-Year data for multiple years (default 2018-2022) and stores
year-keyed snapshots in the trends column for historical analysis.

Usage:
    python -m geohealth.etl.load_trends --state 27
    python -m geohealth.etl.load_trends --state all --start-year 2018 --end-year 2022
"""

from __future__ import annotations

import argparse
import json
import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from geohealth.config import settings
from geohealth.etl.utils import ALL_STATE_FIPS, census_api_get

logger = logging.getLogger(__name__)

ACS_BASE = "https://api.census.gov/data/{year}"

# Variables to fetch for trend tracking
DETAIL_VARS = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_household_income",
    "B01002_001E": "median_age",
}

SUBJECT_VARS = {
    "S1701_C03_001E": "poverty_rate",
    "S2701_C05_001E": "uninsured_rate",
    "S2301_C04_001E": "unemployment_rate",
}

CENSUS_NULL = -666666666

TREND_METRICS = list(DETAIL_VARS.values()) + list(SUBJECT_VARS.values())


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
    df["geoid"] = df["state"] + df["county"] + df["tract"]
    df = df.rename(columns=variables)

    for col in variables.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] == CENSUS_NULL, col] = None

    keep = ["geoid"] + list(variables.values())
    return df[keep]


def _fetch_year(year: int, state_fips: str) -> pd.DataFrame:
    """Fetch detail + subject ACS tables for one year and merge."""
    detail_df = _fetch_table(year, state_fips, "acs/acs5", DETAIL_VARS)
    subject_df = _fetch_table(year, state_fips, "acs/acs5/subject", SUBJECT_VARS)
    return detail_df.merge(subject_df, on="geoid", how="outer")


def load_state(
    state_fips: str,
    engine: Engine,
    start_year: int = 2018,
    end_year: int = 2022,
) -> int:
    """Load multi-year ACS trend data for one state into the trends JSONB column."""
    all_years: dict[str, pd.DataFrame] = {}

    for year in range(start_year, end_year + 1):
        try:
            logger.info("Fetching ACS %d for state %s", year, state_fips)
            df = _fetch_year(year, state_fips)
            all_years[str(year)] = df
            logger.info("Got %d tracts for %d", len(df), year)
        except Exception:
            logger.warning("Failed to fetch ACS %d for state %s — skipping", year, state_fips)
            continue

    if not all_years:
        logger.warning("No trend data fetched for state %s", state_fips)
        return 0

    # Build a geoid → {year: {metrics}} mapping
    geoid_trends: dict[str, dict] = {}
    for year_str, df in all_years.items():
        for _, row in df.iterrows():
            geoid = row["geoid"]
            if geoid not in geoid_trends:
                geoid_trends[geoid] = {}
            snapshot = {}
            for metric in TREND_METRICS:
                val = row.get(metric)
                if pd.notna(val):
                    snapshot[metric] = float(val) if isinstance(val, (int, float)) else val
            geoid_trends[geoid][year_str] = snapshot

    # Write to staging and update
    staging_data = [
        {"geoid": geoid, "trends": json.dumps(trends)}
        for geoid, trends in geoid_trends.items()
    ]
    staging_df = pd.DataFrame(staging_data)
    staging = "_etl_trends_staging"

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))

    staging_df.to_sql(staging, engine, if_exists="replace", index=False)

    update_sql = text(
        f"UPDATE tract_profiles t SET trends = s.trends::jsonb "
        f"FROM {staging} s WHERE t.geoid = s.geoid"
    )

    with engine.begin() as conn:
        result = conn.execute(update_sql)
        updated = result.rowcount
        conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))

    logger.info("Updated trends for %d tracts in state %s", updated, state_fips)
    return updated


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Load multi-year ACS trend data")
    parser.add_argument("--state", type=str, default="all", help="State FIPS or 'all'")
    parser.add_argument("--start-year", type=int, default=2018, help="Start year (default: 2018)")
    parser.add_argument("--end-year", type=int, default=2022, help="End year (default: 2022)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_engine(settings.database_url_sync)
    states = ALL_STATE_FIPS if args.state == "all" else [args.state.zfill(2)]

    total = 0
    for fips in states:
        try:
            total += load_state(fips, engine, args.start_year, args.end_year)
        except Exception:
            logger.exception("Failed to load trends for state %s", fips)

    logger.info("Done — updated trend data for %d tracts total", total)


if __name__ == "__main__":
    main()
