"""Orchestrate all ETL steps for one or more states.

Usage:
    python -m geohealth.etl.load_all --state all
    python -m geohealth.etl.load_all --state 27,06,48
    python -m geohealth.etl.load_all --state all --resume
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from sqlalchemy import create_engine, text

from geohealth.config import settings
from geohealth.etl.utils import ALL_STATE_FIPS

logger = logging.getLogger(__name__)


def _dispatch_webhooks(state_fips: str, step: str, engine) -> None:
    """Fire webhook notifications after a successful ETL step.

    Runs the async dispatch_event in a one-shot event loop so the ETL
    (which is synchronous) doesn't need to be restructured.
    """
    try:
        from sqlalchemy import select as sa_select
        from sqlalchemy.orm import Session
        from geohealth.db.models import WebhookSubscription
        from geohealth.services.webhooks import dispatch_event

        with Session(engine, join_transaction_mode="create_savepoint") as session:
            subs = session.scalars(
                sa_select(WebhookSubscription).where(
                    WebhookSubscription.active.is_(True)
                )
            ).all()
            session.expunge_all()

        if not subs:
            return

        data = {"state_fips": state_fips, "etl_step": step}
        result = asyncio.run(dispatch_event("data.updated", data, subs))
        if result["delivered"] or result["failed"]:
            logger.info(
                "Webhooks for state %s/%s: %d delivered, %d failed",
                state_fips, step, result["delivered"], result["failed"],
            )
    except Exception:
        logger.debug("Webhook dispatch skipped (table may not exist yet)", exc_info=True)


def query_loaded_states(engine) -> set[str]:
    """Return set of state FIPS codes that already have TIGER geometry loaded."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT state_fips FROM tract_profiles WHERE geom IS NOT NULL")
        )
        return {r[0] for r in rows}


def run_pipeline(
    states: list[str],
    year: int,
    places_year: int,
    engine,
    resume: bool = False,
) -> tuple[int, int]:
    """Run the full 5-step ETL pipeline for each state.

    Returns (success_count, failed_count).
    """
    from geohealth.etl import load_tiger, load_acs, load_svi, load_places, compute_sdoh_index

    # Ensure PostGIS + table exist
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    load_tiger.ensure_table(engine)

    # Determine which states to skip TIGER for when resuming
    loaded = query_loaded_states(engine) if resume else set()
    if resume and loaded:
        logger.info("Resume mode: %d states already loaded — skipping TIGER for them", len(loaded))

    # Download SVI national CSV once
    svi_df = None
    try:
        from geohealth.etl.load_svi import _download_svi
        svi_df = _download_svi(year)
    except Exception:
        logger.warning("Failed to download SVI data — SVI step will be skipped for all states")

    success = 0
    failed = 0

    for i, fips in enumerate(states, 1):
        state_start = time.monotonic()
        logger.info("=== State %s (%d/%d) ===", fips, i, len(states))

        try:
            # Step 1: TIGER geometry
            if resume and fips in loaded:
                logger.info("Skipping TIGER for state %s (already loaded)", fips)
            else:
                load_tiger.load_state(year, fips, engine)

            # Step 2: ACS demographics
            load_acs.load_state(year, fips, engine)

            # Step 3: SVI
            if svi_df is not None:
                load_svi.load_state(svi_df, fips, engine)
            else:
                logger.info("Skipping SVI for state %s (download failed)", fips)

            # Step 4: PLACES
            load_places.load_state(fips, engine)

            # Step 5: SDOH index
            compute_sdoh_index.compute_for_state(fips, engine)

            # Notify webhook subscribers
            _dispatch_webhooks(fips, "complete", engine)

            elapsed = time.monotonic() - state_start
            logger.info("State %s completed in %.1fs", fips, elapsed)
            success += 1

        except Exception:
            elapsed = time.monotonic() - state_start
            logger.exception("State %s FAILED after %.1fs", fips, elapsed)
            failed += 1

    return success, failed


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run all ETL steps for one or more states")
    parser.add_argument("--year", type=int, default=2022, help="TIGER/ACS/SVI year (default: 2022)")
    parser.add_argument(
        "--places-year", type=int, default=2023, help="PLACES year (default: 2023)"
    )
    parser.add_argument(
        "--state", type=str, default="all",
        help="'all' or comma-separated FIPS codes (e.g. '27,06,48')",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip TIGER for states already loaded (ACS/SVI/PLACES use upserts)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.state == "all":
        states = ALL_STATE_FIPS
    else:
        states = [s.strip().zfill(2) for s in args.state.split(",")]

    engine = create_engine(settings.database_url_sync)

    total_start = time.monotonic()
    success, failed = run_pipeline(states, args.year, args.places_year, engine, args.resume)
    total_elapsed = time.monotonic() - total_start

    logger.info(
        "=== DONE === %d succeeded, %d failed out of %d states in %.1fs",
        success, failed, len(states), total_elapsed,
    )


if __name__ == "__main__":
    main()
