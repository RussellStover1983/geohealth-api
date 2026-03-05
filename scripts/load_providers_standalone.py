"""Standalone NPI provider loader — uses psycopg2 directly (no SQLAlchemy).

Works around Windows Store Python issue where SQLAlchemy imports hang.
Usage: python scripts/load_providers_standalone.py
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
NPPES_CSV = os.environ.get(
    "NPPES_CSV", r"C:\dev\nppes\npidata_pfile_20050523-20260208.csv"
)
TARGET_STATES = os.environ.get("TARGET_STATES", "GA,KS,MN,MO").split(",")
DB_HOST = os.environ.get("DB_HOST", "yamabiko.proxy.rlwy.net")
DB_PORT = int(os.environ.get("DB_PORT", "44522"))
DB_USER = os.environ.get("DB_USER", "geohealth")
DB_PASS = os.environ.get("DB_PASS", "KUUUUUUuu8u8u8u8u8u8nhtfsdf")
DB_NAME = os.environ.get("DB_NAME", "geohealth")

TAXONOMY_CONFIG = Path(__file__).resolve().parent.parent / "dpc-market-fit" / "app" / "data" / "npi_taxonomy_config.json"
CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints"
CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
BATCH_SIZE = 100  # Census geocoder batch size (small to avoid rate limits)
MAX_RETRIES = 3

# ── Taxonomy loading ────────────────────────────────────────────────────────

def load_taxonomy_sets() -> tuple[set[str], set[str], dict[str, str]]:
    """Load PCP codes, facility codes, and taxonomy descriptions."""
    with open(TAXONOMY_CONFIG) as f:
        config = json.load(f)

    pcp_codes: set[str] = set()
    descriptions: dict[str, str] = {}

    # Parse tiers → tier1/tier2 → codes → {group_name: [{code, description}]}
    tiers = config.get("tiers", {})
    for tier_key in ("tier1", "tier2"):
        tier = tiers.get(tier_key, {})
        codes_dict = tier.get("codes", {})
        for group_name, code_list in codes_dict.items():
            for entry in code_list:
                code = entry.get("code", "")
                desc = entry.get("description", "")
                if code:
                    pcp_codes.add(code)
                    descriptions[code] = desc

    # Parse facility_codes → codes → [{code, description}]
    facility_codes: set[str] = set()
    facility_section = config.get("facility_codes", {})
    for entry in facility_section.get("codes", []):
        code = entry.get("code", "")
        desc = entry.get("description", "")
        if code:
            facility_codes.add(code)
            descriptions[code] = desc

    return pcp_codes, facility_codes, descriptions


def classify_provider_type(taxonomy: str, pcp_codes: set[str], facility_codes: set[str]) -> str | None:
    """Return provider_type string or None if not relevant."""
    if taxonomy in pcp_codes:
        return "pcp"
    if taxonomy == "261QF0400X":
        return "fqhc"
    if taxonomy == "261QU0200X":
        return "urgent_care"
    if taxonomy == "261QR1300X":
        return "rural_health_clinic"
    if taxonomy in facility_codes:
        return "facility"
    return None


# ── NPPES extraction ────────────────────────────────────────────────────────

def extract_providers(nppes_csv: str, states: list[str], pcp_codes: set[str],
                      facility_codes: set[str], descriptions: dict[str, str]) -> list[dict]:
    """Read NPPES CSV and extract relevant providers for target states."""
    all_codes = pcp_codes | facility_codes
    state_set = set(s.upper().strip() for s in states)
    providers: list[dict] = []
    seen_npi: set[str] = set()

    print(f"Reading NPPES CSV: {nppes_csv}")
    print(f"Target states: {state_set}")
    print(f"PCP codes: {len(pcp_codes)}, Facility codes: {len(facility_codes)}")

    with open(nppes_csv, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 500_000 == 0 and i > 0:
                print(f"  Scanned {i:,} rows, found {len(providers):,} providers...")

            npi = (row.get("NPI") or "").strip()
            if not npi or npi in seen_npi:
                continue

            # Check practice state
            state = (row.get("Provider Business Practice Location Address State Name") or "").strip().upper()
            if state not in state_set:
                continue

            # Check taxonomy
            taxonomy = (row.get("Healthcare Provider Taxonomy Code_1") or "").strip()
            if taxonomy not in all_codes:
                continue

            ptype = classify_provider_type(taxonomy, pcp_codes, facility_codes)
            if ptype is None:
                continue

            entity_type = (row.get("Entity Type Code") or "").strip()
            if entity_type == "1":
                first = (row.get("Provider First Name") or "").strip()
                last = (row.get("Provider Last Name (Legal Name)") or "").strip()
                name = f"{first} {last}".strip()
            else:
                name = (row.get("Provider Organization Name (Legal Business Name)") or "").strip()

            providers.append({
                "npi": npi,
                "entity_type": entity_type,
                "provider_name": name,
                "credential": (row.get("Provider Credential Text") or "").strip() or None,
                "gender": (row.get("Provider Gender Code") or "").strip() or None,
                "primary_taxonomy": taxonomy,
                "taxonomy_description": descriptions.get(taxonomy),
                "provider_type": ptype,
                "practice_address": (row.get("Provider First Line Business Practice Location Address") or "").strip(),
                "practice_city": (row.get("Provider Business Practice Location Address City Name") or "").strip(),
                "practice_state": state,
                "practice_zip": (row.get("Provider Business Practice Location Address Postal Code") or "")[:5].strip(),
                "phone": (row.get("Provider Business Practice Location Address Telephone Number") or "").strip() or None,
                "is_fqhc": taxonomy == "261QF0400X",
            })
            seen_npi.add(npi)

    print(f"Extracted {len(providers):,} providers from {i+1:,} rows")
    return providers


# ── Geocoding ───────────────────────────────────────────────────────────────

def _send_census_batch(csv_content: str) -> str:
    """Send a single batch to Census geocoder with retries."""
    boundary = "----CensusBatch"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        f"Public_AR_Current\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="vintage"\r\n\r\n'
        f"Current_Current\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                CENSUS_BATCH_URL,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            wait = 2 ** (attempt + 1)
            print(f"    Retry {attempt+1}/{MAX_RETRIES} after error: {e} (waiting {wait}s)")
            time.sleep(wait)

    raise RuntimeError(f"Census geocoder failed after {MAX_RETRIES} retries")


def _parse_census_response(result_text: str) -> dict[str, dict]:
    """Parse Census batch geocoder response into {npi: {lat, lng, tract_fips}}."""
    result_map: dict[str, dict] = {}
    for line in result_text.strip().split("\n"):
        if not line.strip():
            continue
        reader = csv.reader(io.StringIO(line))
        for parts in reader:
            if len(parts) < 6:
                continue
            npi_id = parts[0].strip()
            match_type = parts[2].strip()
            if match_type != "Match":
                continue
            coords = parts[5].strip()
            if "," not in coords:
                continue
            lon_str, lat_str = coords.split(",", 1)
            try:
                lon = float(lon_str)
                lat = float(lat_str)
            except ValueError:
                continue
            state_fips = parts[8].strip() if len(parts) > 8 else ""
            county_fips = parts[9].strip() if len(parts) > 9 else ""
            tract = parts[10].strip() if len(parts) > 10 else ""
            tract_fips = f"{state_fips}{county_fips}{tract}" if state_fips and county_fips and tract else None
            result_map[npi_id] = {"lat": lat, "lng": lon, "tract_fips": tract_fips}
    return result_map


def geocode_batch_census(providers: list[dict]) -> list[dict]:
    """Geocode providers via Census Bureau batch API with retries."""
    total = len(providers)
    geocoded = 0
    failed = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = providers[batch_start:batch_start + BATCH_SIZE]
        lines = []
        for p in batch:
            lines.append(f'{p["npi"]},{p["practice_address"]},{p["practice_city"]},{p["practice_state"]},{p["practice_zip"]}')
        csv_content = "\n".join(lines)

        try:
            result_text = _send_census_batch(csv_content)
            result_map = _parse_census_response(result_text)

            for p in batch:
                geo = result_map.get(p["npi"])
                if geo:
                    p["lat"] = geo["lat"]
                    p["lng"] = geo["lng"]
                    p["tract_fips"] = geo.get("tract_fips")
                    geocoded += 1
                else:
                    p["lat"] = None
                    p["lng"] = None
                    p["tract_fips"] = None
                    failed += 1

        except Exception as e:
            print(f"  Geocode batch FAILED at {batch_start}: {e}")
            for p in batch:
                p["lat"] = None
                p["lng"] = None
                p["tract_fips"] = None
            failed += len(batch)

        done = batch_start + len(batch)
        if done % 1000 == 0 or done >= total:
            print(f"  Geocoded {done:,}/{total:,} — {geocoded:,} matched, {failed:,} failed")

        # Delay between batches to be kind to Census servers
        time.sleep(0.5)

    return providers


# ── Database insert ─────────────────────────────────────────────────────────

def upsert_providers(providers: list[dict]) -> int:
    """Insert/update providers into npi_providers table using psycopg2.

    Uses individual row inserts with autocommit to avoid long transactions
    that can be killed by the remote server.
    """
    import psycopg2

    # Filter to geocoded only
    geocoded = [p for p in providers if p.get("lat") is not None and p.get("lng") is not None]
    total = len(geocoded)

    sql = """
        INSERT INTO npi_providers (
            npi, entity_type, provider_name, credential, gender,
            primary_taxonomy, taxonomy_description, provider_type,
            practice_address, practice_city, practice_state, practice_zip,
            phone, is_fqhc, tract_fips, geom
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        )
        ON CONFLICT (npi) DO UPDATE SET
            provider_name = EXCLUDED.provider_name,
            credential = EXCLUDED.credential,
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
    """

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME
    )
    inserted = 0
    batch_size = 200

    for batch_start in range(0, total, batch_size):
        batch = geocoded[batch_start:batch_start + batch_size]
        rows = []
        for p in batch:
            rows.append((
                p["npi"], p["entity_type"], p["provider_name"], p.get("credential"),
                p.get("gender"), p["primary_taxonomy"], p.get("taxonomy_description"),
                p["provider_type"], p.get("practice_address"), p.get("practice_city"),
                p["practice_state"], p.get("practice_zip"), p.get("phone"),
                p["is_fqhc"], p.get("tract_fips"),
                p["lng"], p["lat"],
            ))

        try:
            cur = conn.cursor()
            cur.executemany(sql, rows)
            conn.commit()
            cur.close()
            inserted += len(rows)
        except Exception as e:
            print(f"  DB batch error at {batch_start}: {e}")
            # Reconnect and retry
            try:
                conn.close()
            except Exception:
                pass
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME
            )
            try:
                cur = conn.cursor()
                cur.executemany(sql, rows)
                conn.commit()
                cur.close()
                inserted += len(rows)
                print(f"  Retry succeeded for batch at {batch_start}")
            except Exception as e2:
                print(f"  Retry FAILED at {batch_start}: {e2}")
                conn.rollback()

        done = batch_start + len(batch)
        if done % 5000 == 0 or done >= total:
            print(f"  Inserted {done:,}/{total:,}")

    conn.close()
    return inserted


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("NPI Provider Loader (standalone, no SQLAlchemy)")
    print("=" * 60)

    # Load taxonomy config
    pcp_codes, facility_codes, descriptions = load_taxonomy_sets()
    print(f"Loaded {len(pcp_codes)} PCP codes, {len(facility_codes)} facility codes")

    # Extract from NPPES
    providers = extract_providers(NPPES_CSV, TARGET_STATES, pcp_codes, facility_codes, descriptions)
    if not providers:
        print("No providers found! Check NPPES path and target states.")
        sys.exit(1)

    # Check for checkpoint (already geocoded providers)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_file = CHECKPOINT_DIR / "providers_geocoded.json"
    if checkpoint_file.exists():
        print(f"\nLoading checkpoint from {checkpoint_file}...")
        with open(checkpoint_file) as f:
            cached = json.load(f)
        cached_map = {p["npi"]: p for p in cached}
        already_done = 0
        remaining = []
        for p in providers:
            if p["npi"] in cached_map:
                cp = cached_map[p["npi"]]
                p["lat"] = cp.get("lat")
                p["lng"] = cp.get("lng")
                p["tract_fips"] = cp.get("tract_fips")
                already_done += 1
            else:
                remaining.append(p)
        print(f"  Restored {already_done:,} from checkpoint, {len(remaining):,} remaining")
    else:
        remaining = list(providers)

    # Geocode remaining
    if remaining:
        print(f"\nGeocoding {len(remaining):,} providers via Census Bureau batch API...")
        geocode_batch_census(remaining)

        # Save checkpoint
        print("Saving checkpoint...")
        with open(checkpoint_file, "w") as f:
            json.dump(providers, f)

    geocoded_count = sum(1 for p in providers if p.get("lat") is not None)
    print(f"\nGeocoded: {geocoded_count:,} / {len(providers):,}")

    # Insert into DB
    print(f"\nUpserting {geocoded_count:,} geocoded providers into database...")
    inserted = upsert_providers(providers)
    print(f"Done! Inserted/updated {inserted:,} providers.")

    # Summary by state and type
    from collections import Counter
    state_counts = Counter(p["practice_state"] for p in providers if p.get("lat"))
    type_counts = Counter(p["provider_type"] for p in providers if p.get("lat"))
    fqhc_count = sum(1 for p in providers if p.get("lat") and p["is_fqhc"])

    print(f"\nBy state: {dict(state_counts)}")
    print(f"By type: {dict(type_counts)}")
    print(f"FQHCs: {fqhc_count}")


if __name__ == "__main__":
    main()
