"""Compute composite SDOH vulnerability index from loaded data.

Must run after ACS + SVI are loaded. Reads from DB, no external API.

Usage:
    python -m geohealth.etl.compute_sdoh_index --state 27
    python -m geohealth.etl.compute_sdoh_index --state all
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd
from sqlalchemy import create_engine, text

from geohealth.config import settings
from geohealth.etl.utils import ALL_STATE_FIPS, upsert_from_dataframe

logger = logging.getLogger(__name__)

RATE_COLUMNS = ["poverty_rate", "uninsured_rate", "unemployment_rate"]


def compute_for_state(state_fips: str, engine) -> int:
    """Compute sdoh_index for tracts in one state."""
    query = text(
        "SELECT geoid, poverty_rate, uninsured_rate, unemployment_rate, svi_themes "
        "FROM tract_profiles WHERE state_fips = :state"
    )

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"state": state_fips})

    if df.empty:
        logger.warning("No tracts found for state %s", state_fips)
        return 0

    logger.info("Computing sdoh_index for %d tracts in state %s", len(df), state_fips)

    # Min-max normalize rate columns across loaded tracts
    for col in RATE_COLUMNS:
        series = pd.to_numeric(df[col], errors="coerce")
        col_min = series.min()
        col_max = series.max()
        if pd.notna(col_min) and pd.notna(col_max) and col_max > col_min:
            df[f"{col}_norm"] = (series - col_min) / (col_max - col_min)
        else:
            df[f"{col}_norm"] = None

    # Extract SVI overall percentile (rpl_themes) — already 0–1
    def _extract_rpl_themes(svi):
        if svi is None:
            return None
        if isinstance(svi, str):
            import json
            svi = json.loads(svi)
        return svi.get("rpl_themes")

    df["rpl_themes_val"] = df["svi_themes"].apply(_extract_rpl_themes)

    # Composite index = mean of available components
    component_cols = [f"{c}_norm" for c in RATE_COLUMNS] + ["rpl_themes_val"]

    def _mean_available(row):
        vals = [row[c] for c in component_cols if pd.notna(row[c])]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)

    df["sdoh_index"] = df.apply(_mean_available, axis=1)

    result_df = df[["geoid", "sdoh_index"]].copy()
    return upsert_from_dataframe(result_df, engine, ["sdoh_index"])


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Compute composite SDOH vulnerability index")
    parser.add_argument("--state", type=str, default="all", help="State FIPS code or 'all'")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_engine(settings.database_url_sync)
    states = ALL_STATE_FIPS if args.state == "all" else [args.state.zfill(2)]

    total = 0
    for fips in states:
        try:
            total += compute_for_state(fips, engine)
        except Exception:
            logger.exception("Failed to compute sdoh_index for state %s", fips)

    logger.info("Done — updated %d tracts total", total)


if __name__ == "__main__":
    main()
