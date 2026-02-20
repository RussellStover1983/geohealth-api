"""Load CDC/ATSDR Social Vulnerability Index data.

Usage:
    python -m geohealth.etl.load_svi --year 2022 --state 27
    python -m geohealth.etl.load_svi --year 2022 --state all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import httpx
import pandas as pd
from sqlalchemy import create_engine

from geohealth.config import settings
from geohealth.etl.utils import ALL_STATE_FIPS, upsert_from_dataframe

logger = logging.getLogger(__name__)

SVI_URL_TEMPLATE = "https://svi.cdc.gov/Documents/Data/{year}/csv/states/SVI_{year}_US.csv"

SVI_SENTINEL = -999

SVI_COLUMNS = ["RPL_THEME1", "RPL_THEME2", "RPL_THEME3", "RPL_THEME4", "RPL_THEMES"]


def _download_svi(year: int, url_override: str | None = None) -> pd.DataFrame:
    """Download the national SVI CSV and return it as a DataFrame."""
    url = url_override or SVI_URL_TEMPLATE.format(year=year)
    logger.info("Downloading SVI from %s (this may take a moment…)", url)
    resp = httpx.get(url, timeout=300, follow_redirects=True)
    resp.raise_for_status()

    # Read CSV from response content
    from io import StringIO
    df = pd.read_csv(StringIO(resp.text), dtype={"FIPS": str})
    logger.info("Downloaded SVI with %d rows", len(df))
    return df


def load_state(
    svi_df: pd.DataFrame,
    state_fips: str,
    engine,
) -> int:
    """Filter national SVI data for one state and upsert into tract_profiles."""
    # Filter by state FIPS (first 2 chars of the FIPS column)
    state_df = svi_df[svi_df["FIPS"].str[:2] == state_fips].copy()
    logger.info("Found %d SVI rows for state %s", len(state_df), state_fips)

    if state_df.empty:
        return 0

    # Build the JSONB dict per tract
    records = []
    for _, row in state_df.iterrows():
        themes = {}
        for col in SVI_COLUMNS:
            val = row.get(col)
            if pd.notna(val) and val != SVI_SENTINEL:
                themes[col.lower()] = round(float(val), 4)
            else:
                themes[col.lower()] = None

        records.append({
            "geoid": row["FIPS"],
            "svi_themes": json.dumps(themes),
        })

    result_df = pd.DataFrame(records)
    return upsert_from_dataframe(result_df, engine, ["svi_themes"], jsonb_columns=["svi_themes"])


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Load CDC/ATSDR SVI data")
    parser.add_argument("--year", type=int, default=2022, help="SVI year (default: 2022)")
    parser.add_argument("--state", type=str, default="all", help="State FIPS code or 'all'")
    parser.add_argument("--url", type=str, default=None, help="Override SVI download URL")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_engine(settings.database_url_sync)

    # Download the national file once
    svi_df = _download_svi(args.year, args.url)

    states = ALL_STATE_FIPS if args.state == "all" else [args.state.zfill(2)]

    total = 0
    for fips in states:
        try:
            total += load_state(svi_df, fips, engine)
        except Exception:
            logger.exception("Failed to load SVI for state %s", fips)

    logger.info("Done — updated %d tracts total", total)


if __name__ == "__main__":
    main()
