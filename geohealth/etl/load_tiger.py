"""Load TIGER/Line census tract shapefiles into PostGIS.

Usage:
    python -m geohealth.etl.load_tiger --year 2022 --state 27
    python -m geohealth.etl.load_tiger --year 2022 --state all
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

import geopandas as gpd
from sqlalchemy import create_engine, text

from geohealth.config import settings

logger = logging.getLogger(__name__)

TIGER_BASE_URL = "https://www2.census.gov/geo/tiger/TIGER{year}/TRACT"

# All 50 states + DC + territories
ALL_STATE_FIPS = [
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12",
    "13", "15", "16", "17", "18", "19", "20", "21", "22", "23",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "44",
    "45", "46", "47", "48", "49", "50", "51", "53", "54", "55",
    "56", "60", "66", "69", "72", "78",
]


def download_shapefile(year: int, state_fips: str, dest_dir: Path) -> Path:
    filename = f"tl_{year}_{state_fips}_tract.zip"
    url = f"{TIGER_BASE_URL.format(year=year)}/{filename}"
    dest = dest_dir / filename
    logger.info("Downloading %s", url)
    urlretrieve(url, dest)
    return dest


def load_state(year: int, state_fips: str, engine) -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        zippath = download_shapefile(year, state_fips, Path(tmpdir))
        gdf = gpd.read_file(f"zip://{zippath}")

    # Normalise column names to lowercase
    gdf.columns = [c.lower() for c in gdf.columns]

    # Build a DataFrame matching our DB schema
    gdf = gdf.rename(columns={"geometry": "geom"}).set_geometry("geom")
    gdf["geoid"] = gdf["geoid"]
    gdf["state_fips"] = gdf["statefp"]
    gdf["county_fips"] = gdf["countyfp"]
    gdf["tract_code"] = gdf["tractce"]
    gdf["name"] = gdf.get("namelsad", gdf.get("name"))

    keep = ["geoid", "state_fips", "county_fips", "tract_code", "name", "geom"]
    gdf = gdf[keep].copy()

    # Ensure MultiPolygon
    gdf["geom"] = gdf["geom"].apply(
        lambda g: g if g.geom_type == "MultiPolygon" else g.buffer(0) if g is None else gpd.GeoSeries([g]).unary_union
    )
    gdf = gdf.set_geometry("geom")
    gdf = gdf.set_crs(epsg=4326, allow_override=True)

    row_count = len(gdf)
    logger.info("Inserting %d tracts for state FIPS %s", row_count, state_fips)

    # Delete existing rows for this state to ensure idempotency
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM tract_profiles WHERE state_fips = :state"),
            {"state": state_fips},
        )

    gdf.to_postgis(
        "tract_profiles",
        engine,
        if_exists="append",
        index=False,
        dtype={"geom": "Geometry(MULTIPOLYGON, 4326)"},
    )
    return row_count


def ensure_table(engine):
    """Run Alembic migrations to ensure the tract_profiles table exists."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Load TIGER/Line census tract shapefiles")
    parser.add_argument("--year", type=int, default=2022, help="TIGER year (default: 2022)")
    parser.add_argument("--state", type=str, default="all", help="State FIPS code or 'all'")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_engine(settings.database_url_sync)

    # Ensure PostGIS extension
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    ensure_table(engine)

    states = ALL_STATE_FIPS if args.state == "all" else [args.state.zfill(2)]
    total = 0
    for fips in states:
        try:
            total += load_state(args.year, fips, engine)
        except Exception:
            logger.exception("Failed to load state %s", fips)

    logger.info("Done — loaded %d tracts total", total)


if __name__ == "__main__":
    main()
