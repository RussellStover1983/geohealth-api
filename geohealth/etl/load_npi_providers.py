"""ETL: Load individual NPI providers from NPPES bulk CSV into PostGIS.

Reads the pre-extracted NPPES CSV, filters to primary care taxonomy codes
for target states, geocodes via Census Bureau batch geocoder, and upserts
individual provider records into the npi_providers table.

Usage:
    python -m geohealth.etl.load_npi_providers \
        --nppes-csv "C:\\dev\\nppes\\npidata_pfile_20050523-20260208.csv" \
        --states GA,KS,MN,MO

    python -m geohealth.etl.load_npi_providers \
        --nppes-csv /path/to/npidata.csv \
        --states MO --resume
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from geohealth.config import settings
from geohealth.db.models import NpiProvider

logger = logging.getLogger(__name__)

# Taxonomy config from the DPC Market Fit app
_TAXONOMY_CONFIG_PATH = (
    Path(__file__).parent.parent.parent
    / "dpc-market-fit"
    / "app"
    / "data"
    / "npi_taxonomy_config.json"
)

# Checkpoint file for resume support
_CHECKPOINT_DIR = Path(__file__).parent / "_npi_checkpoints"

# Census batch geocoder endpoint
_CENSUS_BATCH_URL = (
    "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
)

# State abbreviation to FIPS mapping (for the 4 target states)
_STATE_ABBREV_TO_FIPS: dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "PR": "72",
    "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48",
    "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}


def _load_taxonomy_sets() -> tuple[set[str], dict[str, str], dict[str, str]]:
    """Load taxonomy code sets from config JSON.

    Returns:
        (pcp_codes, facility_code_to_type, code_to_description)
    """
    with open(_TAXONOMY_CONFIG_PATH) as f:
        config = json.load(f)

    pcp_codes: set[str] = set()
    code_to_desc: dict[str, str] = {}

    for tier_key in ("tier1", "tier2"):
        tier = config["tiers"][tier_key]["codes"]
        for group in tier.values():
            for item in group:
                pcp_codes.add(item["code"])
                code_to_desc[item["code"]] = item["description"]

    facility_code_to_type: dict[str, str] = {}
    for item in config["facility_codes"]["codes"]:
        code = item["code"]
        desc = item["description"].lower()
        code_to_desc[code] = item["description"]
        if "federally qualified" in desc:
            facility_code_to_type[code] = "fqhc"
        elif "urgent care" in desc:
            facility_code_to_type[code] = "urgent_care"
        elif "rural health" in desc:
            facility_code_to_type[code] = "rural_health_clinic"
        elif "primary care clinic" in desc:
            facility_code_to_type[code] = "primary_care_clinic"
        elif "community health" in desc:
            facility_code_to_type[code] = "community_health_center"

    return pcp_codes, facility_code_to_type, code_to_desc


def _extract_taxonomy_codes(row: dict) -> list[str]:
    """Extract all taxonomy codes from an NPPES row (columns 1-15)."""
    codes: list[str] = []
    for i in range(1, 16):
        val = row.get(f"Healthcare Provider Taxonomy Code_{i}", "").strip()
        if val:
            codes.append(val)
    return codes


def _get_primary_taxonomy(row: dict) -> str | None:
    """Get the primary taxonomy code (where switch is 'Y')."""
    for i in range(1, 16):
        code = row.get(f"Healthcare Provider Taxonomy Code_{i}", "").strip()
        switch = row.get(f"Healthcare Provider Primary Taxonomy Switch_{i}", "").strip()
        if code and switch == "Y":
            return code
    # Fallback: return first non-empty code
    for i in range(1, 16):
        code = row.get(f"Healthcare Provider Taxonomy Code_{i}", "").strip()
        if code:
            return code
    return None


def _is_active(row: dict) -> bool:
    """Check if NPI is active (no deactivation date set)."""
    return not row.get("NPI Deactivation Date", "").strip()


def _build_provider_name(row: dict) -> str:
    """Build display name from NPPES row."""
    entity_type = row.get("Entity Type Code", "").strip()
    if entity_type == "2":
        return row.get(
            "Provider Organization Name (Legal Business Name)", ""
        ).strip()
    parts = []
    first = row.get("Provider First Name", "").strip()
    last = row.get("Provider Last Name (Legal Name)", "").strip()
    if first:
        parts.append(first)
    if last:
        parts.append(last)
    return " ".join(parts) or "Unknown"


def extract_providers(
    nppes_csv_path: str,
    pcp_codes: set[str],
    facility_code_to_type: dict[str, str],
    code_to_desc: dict[str, str],
    state_filter: set[str],
    skip_npis: set[str] | None = None,
) -> list[dict]:
    """Extract matching providers from NPPES CSV.

    Returns list of provider dicts ready for geocoding and DB insert.
    """
    all_relevant_codes = pcp_codes | set(facility_code_to_type.keys())
    providers: list[dict] = []
    processed = 0
    matched = 0

    logger.info("Reading NPPES CSV: %s", nppes_csv_path)
    logger.info("Filtering to states: %s", state_filter)

    with open(nppes_csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed += 1
            if processed % 1_000_000 == 0:
                logger.info(
                    "Scanned %d rows, matched %d providers...",
                    processed, matched,
                )

            if not _is_active(row):
                continue

            state = row.get(
                "Provider Business Practice Location Address State Name", ""
            ).strip().upper()
            if state not in state_filter:
                continue

            npi = row.get("NPI", "").strip()
            if not npi:
                continue
            if skip_npis and npi in skip_npis:
                continue

            taxonomy_codes = _extract_taxonomy_codes(row)
            if not taxonomy_codes:
                continue

            # Check if any taxonomy code is relevant
            matching_codes = [c for c in taxonomy_codes if c in all_relevant_codes]
            if not matching_codes:
                continue

            matched += 1
            entity_type = row.get("Entity Type Code", "").strip()
            primary_tax = _get_primary_taxonomy(row)

            # Determine provider_type and is_fqhc
            is_fqhc = any(
                c == "261QF0400X" for c in taxonomy_codes
            )
            provider_type = "pcp"
            for code in matching_codes:
                if code in facility_code_to_type:
                    provider_type = facility_code_to_type[code]
                    break

            address = row.get(
                "Provider First Line Business Practice Location Address", ""
            ).strip()
            city = row.get(
                "Provider Business Practice Location Address City Name", ""
            ).strip()
            zip_raw = row.get(
                "Provider Business Practice Location Address Postal Code", ""
            ).strip()
            practice_zip = zip_raw[:5] if len(zip_raw) >= 5 else None
            phone = row.get(
                "Provider Business Practice Location Address Telephone Number", ""
            ).strip()[:20]

            providers.append({
                "npi": npi[:10],
                "entity_type": entity_type[:1],
                "provider_name": _build_provider_name(row),
                "credential": row.get("Provider Credential Text", "").strip()[:50] or None,
                "gender": row.get("Provider Sex Code", "").strip()[:1] or None,
                "primary_taxonomy": (primary_tax or matching_codes[0])[:15],
                "taxonomy_description": code_to_desc.get(
                    primary_tax or matching_codes[0]
                ),
                "provider_type": provider_type,
                "practice_address": address or None,
                "practice_city": city or None,
                "practice_state": state[:2],
                "practice_zip": practice_zip,
                "phone": phone or None,
                "is_fqhc": is_fqhc,
                # These will be populated by geocoding
                "tract_fips": None,
                "lat": None,
                "lon": None,
            })

    logger.info(
        "Extraction complete: %d rows scanned, %d providers matched",
        processed, matched,
    )
    return providers


def geocode_batch_census(
    providers: list[dict],
    batch_size: int = 1000,
    max_retries: int = 3,
) -> tuple[int, int]:
    """Geocode providers using Census Bureau batch geocoder.

    Modifies providers in-place, setting lat, lon, tract_fips.
    Returns (success_count, fail_count).
    """
    success = 0
    fail = 0
    total = len(providers)

    # Build index by unique ID for lookup
    for idx, p in enumerate(providers):
        p["_geo_idx"] = idx

    # Group into batches
    for batch_start in range(0, total, batch_size):
        batch = providers[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        # Build CSV payload for Census batch geocoder
        csv_lines = []
        for p in batch:
            if not p.get("practice_address") or not p.get("practice_city"):
                fail += 1
                continue
            # Census batch format: UniqueID, Street, City, State, ZIP
            line = ",".join([
                p["npi"],
                p.get("practice_address", "") or "",
                p.get("practice_city", "") or "",
                p.get("practice_state", "") or "",
                p.get("practice_zip", "") or "",
            ])
            csv_lines.append(line)

        if not csv_lines:
            continue

        csv_content = "\n".join(csv_lines)

        for attempt in range(max_retries):
            try:
                resp = httpx.post(
                    _CENSUS_BATCH_URL,
                    data={
                        "benchmark": "Public_AR_Current",
                        "vintage": "Census2020_Current",
                    },
                    files={
                        "addressFile": (
                            "addresses.csv",
                            csv_content.encode("utf-8"),
                            "text/csv",
                        ),
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                break
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Census geocoder batch %d/%d attempt %d failed: %s. "
                        "Retrying in %ds...",
                        batch_num, total_batches, attempt + 1, e, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Census geocoder batch %d/%d failed after %d attempts",
                        batch_num, total_batches, max_retries,
                    )
                    fail += len(csv_lines)
                    continue

        # Parse response — CSV format:
        # "UniqueID","InputAddress","Match","MatchType","MatchedAddress",
        # "Coordinates","TigerLineID","Side","StateFIPS","CountyFIPS",
        # "TractFIPS","BlockFIPS"
        npi_to_provider = {p["npi"]: p for p in batch}
        result_reader = csv.reader(io.StringIO(resp.text))

        for result_row in result_reader:
            if len(result_row) < 8:
                continue
            unique_id = result_row[0].strip().strip('"')
            match_status = result_row[2].strip().strip('"')

            provider = npi_to_provider.get(unique_id)
            if not provider:
                continue

            if match_status in ("Match", "Exact"):
                coords = result_row[5].strip().strip('"')
                if coords and "," in coords:
                    try:
                        lon_str, lat_str = coords.split(",")
                        provider["lon"] = float(lon_str)
                        provider["lat"] = float(lat_str)
                    except (ValueError, IndexError):
                        fail += 1
                        continue

                # Extract tract FIPS: StateFIPS + CountyFIPS + TractFIPS
                state_fips = result_row[8].strip().strip('"') if len(result_row) > 8 else ""
                county_fips = result_row[9].strip().strip('"') if len(result_row) > 9 else ""
                tract_code = result_row[10].strip().strip('"') if len(result_row) > 10 else ""
                if state_fips and county_fips and tract_code:
                    provider["tract_fips"] = f"{state_fips}{county_fips}{tract_code}"

                success += 1
            else:
                fail += 1

        if batch_num % 5 == 0 or batch_num == total_batches:
            logger.info(
                "Geocoding progress: batch %d/%d, %d success, %d fail",
                batch_num, total_batches, success, fail,
            )

        # Small delay between batches to be a good citizen
        time.sleep(0.5)

    logger.info(
        "Geocoding complete: %d success, %d fail out of %d total",
        success, fail, total,
    )
    return success, fail


def upsert_providers(providers: list[dict], engine) -> int:
    """Upsert providers into npi_providers table. Returns count inserted."""
    inserted = 0

    with Session(engine) as session:
        for p in providers:
            if p.get("lat") is None or p.get("lon") is None:
                continue

            geom_wkt = f"SRID=4326;POINT({p['lon']} {p['lat']})"

            session.execute(
                text("""
                    INSERT INTO npi_providers (
                        npi, entity_type, provider_name, credential, gender,
                        primary_taxonomy, taxonomy_description, provider_type,
                        practice_address, practice_city, practice_state,
                        practice_zip, phone, is_fqhc, tract_fips, geom
                    ) VALUES (
                        :npi, :entity_type, :provider_name, :credential, :gender,
                        :primary_taxonomy, :taxonomy_description, :provider_type,
                        :practice_address, :practice_city, :practice_state,
                        :practice_zip, :phone, :is_fqhc, :tract_fips,
                        ST_GeomFromEWKT(:geom)
                    )
                    ON CONFLICT (npi) DO UPDATE SET
                        entity_type = EXCLUDED.entity_type,
                        provider_name = EXCLUDED.provider_name,
                        credential = EXCLUDED.credential,
                        gender = EXCLUDED.gender,
                        primary_taxonomy = EXCLUDED.primary_taxonomy,
                        taxonomy_description = EXCLUDED.taxonomy_description,
                        provider_type = EXCLUDED.provider_type,
                        practice_address = EXCLUDED.practice_address,
                        practice_city = EXCLUDED.practice_city,
                        practice_state = EXCLUDED.practice_state,
                        practice_zip = EXCLUDED.practice_zip,
                        phone = EXCLUDED.phone,
                        is_fqhc = EXCLUDED.is_fqhc,
                        tract_fips = EXCLUDED.tract_fips,
                        geom = EXCLUDED.geom
                """),
                {
                    "npi": p["npi"],
                    "entity_type": p["entity_type"],
                    "provider_name": p["provider_name"],
                    "credential": p["credential"],
                    "gender": p["gender"],
                    "primary_taxonomy": p["primary_taxonomy"],
                    "taxonomy_description": p["taxonomy_description"],
                    "provider_type": p["provider_type"],
                    "practice_address": p["practice_address"],
                    "practice_city": p["practice_city"],
                    "practice_state": p["practice_state"],
                    "practice_zip": p["practice_zip"],
                    "phone": p["phone"],
                    "is_fqhc": p["is_fqhc"],
                    "tract_fips": p.get("tract_fips"),
                    "geom": geom_wkt,
                },
            )
            inserted += 1

            if inserted % 1000 == 0:
                session.commit()
                logger.info("Upserted %d providers...", inserted)

        session.commit()

    logger.info("Upsert complete: %d providers inserted/updated", inserted)
    return inserted


def save_checkpoint(state: str, providers: list[dict]) -> None:
    """Save geocoded providers to checkpoint file for resume."""
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = _CHECKPOINT_DIR / f"providers_{state}.json"
    # Save only the fields we need
    slim = []
    for p in providers:
        slim.append({
            "npi": p["npi"],
            "entity_type": p["entity_type"],
            "provider_name": p["provider_name"],
            "credential": p["credential"],
            "gender": p["gender"],
            "primary_taxonomy": p["primary_taxonomy"],
            "taxonomy_description": p["taxonomy_description"],
            "provider_type": p["provider_type"],
            "practice_address": p["practice_address"],
            "practice_city": p["practice_city"],
            "practice_state": p["practice_state"],
            "practice_zip": p["practice_zip"],
            "phone": p["phone"],
            "is_fqhc": p["is_fqhc"],
            "tract_fips": p.get("tract_fips"),
            "lat": p.get("lat"),
            "lon": p.get("lon"),
        })
    with open(path, "w") as f:
        json.dump(slim, f)
    logger.info("Saved checkpoint for %s: %d providers", state, len(slim))


def load_checkpoint(state: str) -> list[dict] | None:
    """Load checkpoint file if it exists."""
    path = _CHECKPOINT_DIR / f"providers_{state}.json"
    if path.exists():
        with open(path) as f:
            providers = json.load(f)
        logger.info("Loaded checkpoint for %s: %d providers", state, len(providers))
        return providers
    return None


def run_etl(
    nppes_csv_path: str,
    states: set[str],
    resume: bool = False,
) -> None:
    """Run the full ETL pipeline."""
    # Get sync DB URL
    db_url = settings.database_url_sync
    logger.info("Connecting to database...")
    engine = create_engine(db_url, echo=False)

    # Ensure table exists
    NpiProvider.__table__.create(engine, checkfirst=True)

    # Load taxonomy config
    pcp_codes, facility_code_to_type, code_to_desc = _load_taxonomy_sets()
    logger.info(
        "Loaded %d PCP codes, %d facility codes",
        len(pcp_codes), len(facility_code_to_type),
    )

    for state in sorted(states):
        logger.info("=" * 60)
        logger.info("Processing state: %s", state)
        logger.info("=" * 60)

        # Check for resume checkpoint
        if resume:
            checkpoint = load_checkpoint(state)
            if checkpoint:
                logger.info(
                    "Resuming from checkpoint: %d providers for %s",
                    len(checkpoint), state,
                )
                count = upsert_providers(checkpoint, engine)
                logger.info("State %s: upserted %d providers from checkpoint", state, count)
                continue

        # Extract providers for this state
        providers = extract_providers(
            nppes_csv_path,
            pcp_codes,
            facility_code_to_type,
            code_to_desc,
            state_filter={state},
        )

        if not providers:
            logger.warning("No providers found for state %s", state)
            continue

        logger.info("Found %d providers for %s, starting geocoding...", len(providers), state)

        # Geocode
        success, fail = geocode_batch_census(providers)
        geocoded = [p for p in providers if p.get("lat") is not None]
        logger.info(
            "State %s: %d geocoded, %d failed",
            state, len(geocoded), len(providers) - len(geocoded),
        )

        # Save checkpoint
        save_checkpoint(state, providers)

        # Upsert to DB
        count = upsert_providers(providers, engine)
        logger.info("State %s complete: %d providers loaded", state, count)

    logger.info("=" * 60)
    logger.info("ETL complete for all states")
    logger.info("=" * 60)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load individual NPI providers from NPPES into PostGIS"
    )
    parser.add_argument(
        "--nppes-csv",
        required=True,
        help="Path to extracted NPPES npidata CSV file",
    )
    parser.add_argument(
        "--states",
        required=True,
        help="Comma-separated 2-letter state codes (e.g., GA,KS,MN,MO)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint files if available",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    states = {s.strip().upper() for s in args.states.split(",")}
    run_etl(args.nppes_csv, states, resume=args.resume)


if __name__ == "__main__":
    main()
