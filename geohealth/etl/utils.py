"""Shared ETL utilities for GeoHealth data loading."""

from __future__ import annotations

import logging
import time

import httpx
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from geohealth.config import settings

logger = logging.getLogger(__name__)

# All 50 states + DC + territories
ALL_STATE_FIPS = [
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12",
    "13", "15", "16", "17", "18", "19", "20", "21", "22", "23",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "44",
    "45", "46", "47", "48", "49", "50", "51", "53", "54", "55",
    "56", "60", "66", "69", "72", "78",
]


def upsert_from_dataframe(
    df: pd.DataFrame,
    engine: Engine,
    update_columns: list[str],
    jsonb_columns: list[str] | None = None,
) -> int:
    """Write df to a staging table, then UPDATE tract_profiles from it.

    The DataFrame must have a 'geoid' column for joining.
    Columns listed in *jsonb_columns* are cast to JSONB in the UPDATE.
    Returns the number of rows updated.
    """
    jsonb_columns = set(jsonb_columns or [])
    staging = "_etl_staging"

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))

    df.to_sql(staging, engine, if_exists="replace", index=False)

    parts = []
    for col in update_columns:
        if col in jsonb_columns:
            parts.append(f"{col} = s.{col}::jsonb")
        else:
            parts.append(f"{col} = s.{col}")
    set_clause = ", ".join(parts)
    update_sql = text(
        f"UPDATE tract_profiles t SET {set_clause} "
        f"FROM {staging} s WHERE t.geoid = s.geoid"
    )

    with engine.begin() as conn:
        result = conn.execute(update_sql)
        updated = result.rowcount
        conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))

    logger.info("Updated %d rows in tract_profiles", updated)
    return updated


def census_api_get(url: str, params: dict | None = None) -> httpx.Response:
    """GET from the Census Bureau API with optional API key injection and retry on 429."""
    params = dict(params or {})
    if settings.census_api_key:
        params["key"] = settings.census_api_key

    max_retries = 3
    for attempt in range(max_retries):
        resp = httpx.get(url, params=params, timeout=60)
        if resp.status_code == 429:
            wait = 2 ** attempt
            logger.warning("Rate limited (429), retrying in %ds…", wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp

    resp.raise_for_status()
    return resp
