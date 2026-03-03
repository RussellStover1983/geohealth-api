"""NPPES Bulk Data ETL — tract-level provider counts via HUD ZIP-Tract crosswalk.

Downloads the NPPES monthly data dissemination CSV (~9.3GB zipped),
filters to primary care taxonomy codes, geocodes practice addresses
to census tracts using the HUD USPS ZIP-to-Tract crosswalk, and
produces a pre-computed npi_tract_counts.csv with tract-level PCP
and facility counts.

Usage:
    python -m etl.load_npi_tract --nppes-zip /path/to/NPPES_Data_*.zip \
        --hud-crosswalk /path/to/ZIP_TRACT_*.xlsx

    python -m etl.load_npi_tract --download   # download both files automatically
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Output path
_OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "npi_tract_counts.csv"

# Load taxonomy codes from config
_TAXONOMY_CONFIG_PATH = Path(__file__).parent.parent / "app" / "data" / "npi_taxonomy_config.json"


def _load_taxonomy_sets() -> tuple[set[str], dict[str, str]]:
    """Load taxonomy code sets from config JSON.

    Returns:
        (pcp_codes, facility_code_to_column): PCP taxonomy codes (tier1+tier2)
        and facility codes mapped to CSV column names.
    """
    import json

    with open(_TAXONOMY_CONFIG_PATH) as f:
        config = json.load(f)

    pcp_codes: set[str] = set()
    for tier_key in ("tier1", "tier2"):
        tier = config["tiers"][tier_key]["codes"]
        for group in tier.values():
            for item in group:
                pcp_codes.add(item["code"])

    # Map facility codes to output column names
    facility_code_to_column: dict[str, str] = {}
    for item in config["facility_codes"]["codes"]:
        code = item["code"]
        desc = item["description"].lower()
        if "federally qualified" in desc or "fqhc" in desc.lower():
            facility_code_to_column[code] = "fqhc_count"
        elif "urgent care" in desc:
            facility_code_to_column[code] = "urgent_care_count"
        elif "rural health" in desc:
            facility_code_to_column[code] = "rural_health_clinic_count"
        elif "primary care clinic" in desc:
            facility_code_to_column[code] = "primary_care_clinic_count"
        elif "community health" in desc:
            facility_code_to_column[code] = "community_health_center_count"

    return pcp_codes, facility_code_to_column


def load_hud_crosswalk(crosswalk_path: str) -> dict[str, list[tuple[str, float]]]:
    """Load HUD USPS ZIP-Tract crosswalk into a dict: ZIP -> [(tract_fips, ratio), ...].

    Supports both .xlsx and .csv formats. Uses TOT_RATIO for allocation.
    """
    crosswalk: dict[str, list[tuple[str, float]]] = {}

    if crosswalk_path.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError:
            logger.error("openpyxl required for .xlsx files: pip install openpyxl")
            raise

        wb = openpyxl.load_workbook(crosswalk_path, read_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header = [str(c).strip().upper() if c else "" for c in next(rows)]

        zip_idx = header.index("ZIP")
        tract_idx = header.index("TRACT")
        ratio_idx = header.index("TOT_RATIO")

        for row in rows:
            zip_code = str(row[zip_idx]).strip().zfill(5)[:5]
            tract_fips = str(row[tract_idx]).strip()
            ratio = float(row[ratio_idx]) if row[ratio_idx] else 0.0

            if len(tract_fips) == 11 and ratio > 0:
                if zip_code not in crosswalk:
                    crosswalk[zip_code] = []
                crosswalk[zip_code].append((tract_fips, ratio))

        wb.close()
    else:
        # CSV format
        with open(crosswalk_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                zip_code = row.get("ZIP", "").strip().zfill(5)[:5]
                tract_fips = row.get("TRACT", "").strip()
                ratio_str = row.get("TOT_RATIO", "0")
                try:
                    ratio = float(ratio_str)
                except (ValueError, TypeError):
                    ratio = 0.0

                if len(tract_fips) == 11 and ratio > 0:
                    if zip_code not in crosswalk:
                        crosswalk[zip_code] = []
                    crosswalk[zip_code].append((tract_fips, ratio))

    logger.info(
        "Loaded HUD crosswalk: %d ZIP codes -> tract mappings", len(crosswalk)
    )
    return crosswalk


def load_census_zcta_crosswalk(
    crosswalk_path: str,
) -> dict[str, list[tuple[str, float]]]:
    """Load Census ZCTA-to-Tract relationship file into ZIP -> [(tract, ratio), ...].

    Uses AREALAND_PART / AREALAND_ZCTA5_20 as the allocation ratio.
    The Census file is pipe-delimited with a BOM header.
    """
    from collections import defaultdict

    # First pass: accumulate area parts per ZCTA
    zcta_tracts: dict[str, list[tuple[str, float, float]]] = defaultdict(list)

    with open(crosswalk_path, encoding="utf-8-sig") as f:
        header_line = f.readline().strip()
        headers = header_line.split("|")

        zcta_idx = headers.index("GEOID_ZCTA5_20")
        tract_idx = headers.index("GEOID_TRACT_20")
        zcta_area_idx = headers.index("AREALAND_ZCTA5_20")
        part_area_idx = headers.index("AREALAND_PART")

        for line in f:
            parts = line.strip().split("|")
            if len(parts) <= max(zcta_idx, tract_idx, zcta_area_idx, part_area_idx):
                continue

            zcta = parts[zcta_idx].strip()
            tract_fips = parts[tract_idx].strip()

            if not zcta or not tract_fips or len(tract_fips) != 11:
                continue

            try:
                zcta_area = float(parts[zcta_area_idx])
                part_area = float(parts[part_area_idx])
            except (ValueError, TypeError):
                continue

            if zcta_area > 0 and part_area > 0:
                ratio = part_area / zcta_area
                zcta_tracts[zcta].append((tract_fips, ratio, part_area))

    # Normalize ratios per ZCTA so they sum to ~1.0
    crosswalk: dict[str, list[tuple[str, float]]] = {}
    for zcta, tract_list in zcta_tracts.items():
        total_ratio = sum(r for _, r, _ in tract_list)
        if total_ratio > 0:
            normalized = [
                (tract, r / total_ratio) for tract, r, _ in tract_list
            ]
            # Filter out tiny slivers (<0.1% allocation)
            normalized = [(t, r) for t, r in normalized if r >= 0.001]
            if normalized:
                crosswalk[zcta] = normalized

    logger.info(
        "Loaded Census ZCTA crosswalk: %d ZCTAs -> tract mappings",
        len(crosswalk),
    )
    return crosswalk


def load_crosswalk(crosswalk_path: str) -> dict[str, list[tuple[str, float]]]:
    """Auto-detect and load crosswalk file (HUD or Census format)."""
    # Census ZCTA file is pipe-delimited with specific header
    with open(crosswalk_path, encoding="utf-8-sig") as f:
        first_line = f.readline()

    if "GEOID_ZCTA5_20" in first_line:
        return load_census_zcta_crosswalk(crosswalk_path)
    else:
        return load_hud_crosswalk(crosswalk_path)


def _extract_taxonomy_codes(row: dict) -> list[str]:
    """Extract all taxonomy codes from an NPPES row (columns 1-15)."""
    codes: list[str] = []
    for i in range(1, 16):
        col = f"Healthcare Provider Taxonomy Code_{i}"
        val = row.get(col, "").strip()
        if val:
            codes.append(val)
    return codes


def _get_practice_zip(row: dict) -> str | None:
    """Extract 5-digit practice ZIP from NPPES row."""
    raw = row.get(
        "Provider Business Practice Location Address Postal Code", ""
    ).strip()
    if raw and len(raw) >= 5:
        return raw[:5]
    return None


def _is_active(row: dict) -> bool:
    """Check if NPI is active (deactivation reason is empty)."""
    return not row.get("NPI Deactivation Reason Code", "").strip()


def process_nppes_stream(
    nppes_reader: csv.DictReader,
    crosswalk: dict[str, list[tuple[str, float]]],
    pcp_codes: set[str],
    facility_code_to_column: dict[str, str],
    *,
    state_filter: set[str] | None = None,
) -> dict[str, dict[str, float]]:
    """Stream-process NPPES CSV rows and allocate to tracts.

    Args:
        nppes_reader: CSV DictReader over NPPES data
        crosswalk: ZIP -> [(tract_fips, ratio), ...]
        pcp_codes: Set of tier1+tier2 PCP taxonomy codes
        facility_code_to_column: Facility code -> column name mapping
        state_filter: Optional set of 2-letter state codes to include

    Returns:
        Dict of tract_fips -> {pcp_count, fqhc_count, ...}
    """
    all_facility_codes = set(facility_code_to_column.keys())
    tract_counts: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "pcp_count": 0.0,
            "fqhc_count": 0.0,
            "urgent_care_count": 0.0,
            "rural_health_clinic_count": 0.0,
            "primary_care_clinic_count": 0.0,
            "community_health_center_count": 0.0,
        }
    )

    processed = 0
    matched = 0
    skipped_inactive = 0
    skipped_no_zip = 0
    skipped_no_crosswalk = 0

    for row in nppes_reader:
        processed += 1
        if processed % 500_000 == 0:
            logger.info(
                "Processed %d rows, matched %d providers...",
                processed, matched,
            )

        # Skip inactive NPIs
        if not _is_active(row):
            skipped_inactive += 1
            continue

        # Optional state filter
        if state_filter:
            state = row.get(
                "Provider Business Practice Location Address State Name", ""
            ).strip().upper()
            if state not in state_filter:
                continue

        # Get taxonomy codes for this row
        taxonomy_codes = _extract_taxonomy_codes(row)
        if not taxonomy_codes:
            continue

        entity_type = row.get("Entity Type Code", "").strip()

        # Determine what this provider counts as
        is_pcp = False
        facility_columns: list[str] = []

        if entity_type == "1":
            # Individual provider — check PCP taxonomy
            for code in taxonomy_codes:
                if code in pcp_codes:
                    is_pcp = True
                    break
        elif entity_type == "2":
            # Organization — check facility codes
            for code in taxonomy_codes:
                if code in all_facility_codes:
                    col = facility_code_to_column[code]
                    if col not in facility_columns:
                        facility_columns.append(col)

        if not is_pcp and not facility_columns:
            continue

        # Get practice ZIP
        practice_zip = _get_practice_zip(row)
        if not practice_zip:
            skipped_no_zip += 1
            continue

        # Look up tracts from crosswalk
        tracts = crosswalk.get(practice_zip)
        if not tracts:
            skipped_no_crosswalk += 1
            continue

        matched += 1

        # Allocate fractionally across tracts
        for tract_fips, ratio in tracts:
            if is_pcp:
                tract_counts[tract_fips]["pcp_count"] += ratio
            for col in facility_columns:
                tract_counts[tract_fips][col] += ratio

    logger.info(
        "NPPES processing complete: %d rows processed, %d matched, "
        "%d inactive, %d no ZIP, %d no crosswalk match",
        processed, matched, skipped_inactive, skipped_no_zip,
        skipped_no_crosswalk,
    )

    return dict(tract_counts)


def write_output_csv(
    tract_counts: dict[str, dict[str, float]],
    output_path: Path | str,
) -> None:
    """Write tract-level NPI counts to CSV."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "tract_fips",
        "pcp_count",
        "fqhc_count",
        "urgent_care_count",
        "rural_health_clinic_count",
        "primary_care_clinic_count",
        "community_health_center_count",
        "total_providers",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for tract_fips in sorted(tract_counts.keys()):
            counts = tract_counts[tract_fips]
            total = sum(counts.values())
            writer.writerow({
                "tract_fips": tract_fips,
                "pcp_count": round(counts["pcp_count"], 1),
                "fqhc_count": round(counts["fqhc_count"], 1),
                "urgent_care_count": round(counts["urgent_care_count"], 1),
                "rural_health_clinic_count": round(
                    counts["rural_health_clinic_count"], 1
                ),
                "primary_care_clinic_count": round(
                    counts["primary_care_clinic_count"], 1
                ),
                "community_health_center_count": round(
                    counts["community_health_center_count"], 1
                ),
                "total_providers": round(total, 1),
            })

    logger.info(
        "Wrote %d tract rows to %s", len(tract_counts), output_path
    )


def download_nppes_zip(dest_dir: str) -> str:
    """Download NPPES Full Data Dissemination ZIP from CMS.

    Returns path to the downloaded ZIP file.
    """
    import httpx

    # CMS distributes via a download page; the actual ZIP URL changes monthly
    # We use the known pattern for the full replacement file
    download_url = (
        "https://download.cms.gov/nppes/NPPES_Data_Dissemination_March_2026.zip"
    )

    dest_path = os.path.join(dest_dir, "nppes_full.zip")
    logger.info("Downloading NPPES data from %s ...", download_url)

    with httpx.stream("GET", download_url, timeout=600, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    if downloaded % (100 * 1024 * 1024) < 1024 * 1024:
                        logger.info("Downloaded %.0f%% (%d MB)", pct, downloaded // (1024 * 1024))

    logger.info("NPPES download complete: %s", dest_path)
    return dest_path


def download_hud_crosswalk(dest_dir: str) -> str:
    """Download HUD USPS ZIP-Tract crosswalk.

    Returns path to the downloaded file.
    """
    import httpx

    # HUD crosswalk download URL (quarterly updates)
    download_url = (
        "https://www.huduser.gov/portal/datasets/usps/ZIP_TRACT_032026.xlsx"
    )

    dest_path = os.path.join(dest_dir, "zip_tract_crosswalk.xlsx")
    logger.info("Downloading HUD crosswalk from %s ...", download_url)

    with httpx.stream("GET", download_url, timeout=120, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)

    logger.info("HUD crosswalk download complete: %s", dest_path)
    return dest_path


def run_etl(
    nppes_zip_path: str,
    hud_crosswalk_path: str,
    output_path: str | None = None,
    state_filter: set[str] | None = None,
) -> Path:
    """Run the full ETL pipeline.

    Args:
        nppes_zip_path: Path to NPPES ZIP file
        hud_crosswalk_path: Path to HUD crosswalk (.xlsx or .csv)
        output_path: Output CSV path (defaults to app/data/npi_tract_counts.csv)
        state_filter: Optional set of 2-letter state codes to include

    Returns:
        Path to the output CSV file.
    """
    out = Path(output_path) if output_path else _OUTPUT_PATH

    # Load taxonomy config
    pcp_codes, facility_code_to_column = _load_taxonomy_sets()
    logger.info(
        "Loaded %d PCP codes, %d facility codes",
        len(pcp_codes), len(facility_code_to_column),
    )

    # Load crosswalk (auto-detects HUD vs Census format)
    crosswalk = load_crosswalk(hud_crosswalk_path)

    # Process NPPES ZIP — find the main CSV inside
    logger.info("Opening NPPES ZIP: %s", nppes_zip_path)

    with zipfile.ZipFile(nppes_zip_path, "r") as zf:
        # Find the main NPI data file (largest CSV, typically named npidata_*.csv)
        csv_files = [
            name for name in zf.namelist()
            if name.lower().endswith(".csv") and "npidata" in name.lower()
        ]
        if not csv_files:
            # Fall back to any CSV
            csv_files = [
                name for name in zf.namelist()
                if name.lower().endswith(".csv")
            ]
        if not csv_files:
            raise FileNotFoundError("No CSV files found in NPPES ZIP")

        # Pick the largest CSV
        csv_file = max(csv_files, key=lambda n: zf.getinfo(n).file_size)
        logger.info("Processing NPPES CSV: %s", csv_file)

        with zf.open(csv_file) as raw:
            text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_stream)

            tract_counts = process_nppes_stream(
                reader,
                crosswalk,
                pcp_codes,
                facility_code_to_column,
                state_filter=state_filter,
            )

    # Write output
    write_output_csv(tract_counts, out)
    return out


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NPPES Bulk Data ETL — tract-level provider counts"
    )
    parser.add_argument(
        "--nppes-zip",
        help="Path to NPPES Data Dissemination ZIP file",
    )
    parser.add_argument(
        "--hud-crosswalk",
        help="Path to HUD USPS ZIP-Tract crosswalk file (.xlsx or .csv)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download NPPES and HUD crosswalk files automatically",
    )
    parser.add_argument(
        "--output",
        help="Output CSV path (default: app/data/npi_tract_counts.csv)",
    )
    parser.add_argument(
        "--states",
        help="Comma-separated 2-letter state codes to filter (e.g., MO,KS,MN)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    state_filter = None
    if args.states:
        state_filter = {s.strip().upper() for s in args.states.split(",")}
        logger.info("Filtering to states: %s", state_filter)

    if args.download:
        with tempfile.TemporaryDirectory() as tmp:
            nppes_path = download_nppes_zip(tmp)
            hud_path = download_hud_crosswalk(tmp)
            run_etl(nppes_path, hud_path, args.output, state_filter)
    elif args.nppes_zip and args.hud_crosswalk:
        run_etl(args.nppes_zip, args.hud_crosswalk, args.output, state_filter)
    else:
        parser.error(
            "Provide --nppes-zip and --hud-crosswalk, or use --download"
        )


if __name__ == "__main__":
    main()
