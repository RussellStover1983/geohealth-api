"""Load CDC PLACES health measures from the Socrata API.

Usage:
    python -m geohealth.etl.load_places --year 2023 --state 27
    python -m geohealth.etl.load_places --year 2023 --state all
"""

from __future__ import annotations

import argparse
import json
import logging

import httpx
import pandas as pd
from sqlalchemy import create_engine

from geohealth.config import settings
from geohealth.etl.utils import ALL_STATE_FIPS, upsert_from_dataframe

logger = logging.getLogger(__name__)

PLACES_API = "https://data.cdc.gov/resource/cwsq-ngmh.json"

PLACES_MEASURES = [
    "DIABETES", "OBESITY", "MHLTH", "PHLTH", "BPHIGH", "CASTHMA",
    "CHD", "CSMOKING", "ACCESS2", "CHECKUP", "DENTAL", "SLEEP",
    "LPA", "BINGE",
]

PAGE_SIZE = 50000


def _fetch_places(state_fips: str) -> pd.DataFrame:
    """Paginate through the Socrata PLACES API for one state."""
    headers = {}
    if settings.socrata_app_token:
        headers["X-App-Token"] = settings.socrata_app_token

    all_rows: list[dict] = []
    offset = 0

    while True:
        params = {
            "$where": f"starts_with(locationid, '{state_fips}') "
                      f"AND data_value_type='Crude prevalence'",
            "$limit": str(PAGE_SIZE),
            "$offset": str(offset),
        }

        logger.info("Fetching PLACES offset=%d for state %s", offset, state_fips)
        resp = httpx.get(PLACES_API, params=params, headers=headers, timeout=120)
        resp.raise_for_status()

        page = resp.json()
        if not page:
            break

        all_rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    logger.info("Fetched %d PLACES rows for state %s", len(all_rows), state_fips)
    return pd.DataFrame(all_rows)


def load_state(state_fips: str, engine) -> int:
    """Fetch PLACES data for one state, pivot to JSONB, and upsert."""
    raw_df = _fetch_places(state_fips)

    if raw_df.empty:
        logger.warning("No PLACES data for state %s", state_fips)
        return 0

    # Filter to our target measures and tract-level data
    raw_df = raw_df[raw_df["measureid"].isin(PLACES_MEASURES)].copy()
    raw_df = raw_df[raw_df["locationid"].str.len() == 11].copy()  # tract-level GEOIDs only

    if raw_df.empty:
        logger.warning("No tract-level PLACES measures for state %s", state_fips)
        return 0

    # Convert data_value to float
    raw_df["data_value"] = pd.to_numeric(raw_df["data_value"], errors="coerce")

    # Pivot: one row per tract, one column per measure
    pivot = raw_df.pivot_table(
        index="locationid",
        columns="measureid",
        values="data_value",
        aggfunc="first",
    )

    # Build JSONB dict per tract
    records = []
    for geoid, row in pivot.iterrows():
        measures = {}
        for m in PLACES_MEASURES:
            val = row.get(m)
            if pd.notna(val):
                measures[m.lower()] = round(float(val), 1)
            else:
                measures[m.lower()] = None
        records.append({
            "geoid": geoid,
            "places_measures": json.dumps(measures),
        })

    result_df = pd.DataFrame(records)
    return upsert_from_dataframe(
        result_df, engine, ["places_measures"], jsonb_columns=["places_measures"]
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Load CDC PLACES health measures")
    parser.add_argument("--year", type=int, default=2023, help="PLACES year (default: 2023)")
    parser.add_argument("--state", type=str, default="all", help="State FIPS code or 'all'")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_engine(settings.database_url_sync)
    states = ALL_STATE_FIPS if args.state == "all" else [args.state.zfill(2)]

    total = 0
    for fips in states:
        try:
            total += load_state(fips, engine)
        except Exception:
            logger.exception("Failed to load PLACES for state %s", fips)

    logger.info("Done — updated %d tracts total", total)


if __name__ == "__main__":
    main()
