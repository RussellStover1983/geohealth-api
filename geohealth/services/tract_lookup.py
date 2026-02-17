from __future__ import annotations

import logging

from geoalchemy2.functions import ST_Contains, ST_Point, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.db.models import TractProfile

logger = logging.getLogger(__name__)


async def lookup_tract(
    lat: float,
    lng: float,
    session: AsyncSession,
    *,
    state_fips: str | None = None,
    county_fips: str | None = None,
    tract_fips: str | None = None,
) -> TractProfile | None:
    """Find the census tract containing (lat, lng) via PostGIS point-in-polygon.

    Falls back to constructing a GEOID from FIPS codes provided by the Census
    geocoder if PostGIS geometry isn't loaded yet.
    """
    point = ST_SetSRID(ST_Point(lng, lat), 4326)
    stmt = select(TractProfile).where(ST_Contains(TractProfile.geom, point))
    result = await session.execute(stmt)
    tract = result.scalar_one_or_none()

    if tract is not None:
        return tract

    # Fallback: look up by GEOID if FIPS parts were provided
    if state_fips and county_fips and tract_fips:
        geoid = f"{state_fips}{county_fips}{tract_fips}"
        logger.info("PostGIS miss; falling back to GEOID lookup: %s", geoid)
        stmt = select(TractProfile).where(TractProfile.geoid == geoid)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    return None
