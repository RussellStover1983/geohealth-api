from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from geohealth.api.dependencies import get_db
from geohealth.api.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from geohealth.api.middleware import RequestLoggingMiddleware
from geohealth.api.routes.batch import router as batch_router
from geohealth.api.routes.compare import router as compare_router
from geohealth.api.routes.context import router as context_router
from geohealth.api.routes.nearby import router as nearby_router
from geohealth.api.routes.stats import router as stats_router
from geohealth.api.schemas import ErrorResponse, HealthResponse
from geohealth.config import settings
from geohealth.db.session import engine
from geohealth.logging_config import setup_logging
from geohealth.services.cache import context_cache
from geohealth.services.metrics import metrics
from geohealth.services.rate_limiter import rate_limiter

logger = logging.getLogger("geohealth")

_DESCRIPTION = """\
Census-tract-level geographic health intelligence API.

Given a street address or lat/lng coordinates, returns **demographics**,
**CDC/ATSDR Social Vulnerability Index (SVI) themes**,
**CDC PLACES health outcome measures**, and an optional
**AI-generated narrative** for the surrounding census tract.

### Data resolution

All data is resolved to the **census tract** level (~4,000 residents per
tract on average). Coordinates are matched to tracts via PostGIS spatial
queries or FIPS-code lookups from the Census Bureau geocoder.

### Authentication

Most endpoints require an API key passed via the `X-API-Key` header.
See the *Authentication* section in the README for details on key
management and SHA-256 pre-hashing.

### Rate limiting

Requests are rate-limited per API key using a sliding window.
Every response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
and `X-RateLimit-Reset` headers.
"""

_OPENAPI_TAGS = [
    {
        "name": "system",
        "description": "Health checks and operational endpoints.",
    },
    {
        "name": "context",
        "description": (
            "Primary lookup — resolve an address or coordinates to "
            "census tract demographics, SVI themes, PLACES measures, "
            "and an optional AI narrative."
        ),
    },
    {
        "name": "batch",
        "description": (
            "Batch address lookups — submit multiple addresses in a "
            "single request and receive per-address results."
        ),
    },
    {
        "name": "nearby",
        "description": (
            "Spatial radius search — find census tracts within a "
            "given distance of a point, sorted by proximity."
        ),
    },
    {
        "name": "compare",
        "description": (
            "Compare two census tracts side-by-side, or compare a "
            "tract against state or national averages."
        ),
    },
    {
        "name": "stats",
        "description": (
            "Data loading statistics — view total tracts loaded "
            "and per-state breakdowns."
        ),
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, settings.log_format)

    # Temporary: log auth config to diagnose 403 (remove once verified)
    from geohealth.api.auth import _valid_key_hashes, _hash_key
    _hashes = _valid_key_hashes()
    logger.warning(
        "AUTH DEBUG: api_keys=%r, parsed_hashes=%d, test_hash=%s, match=%s",
        settings.api_keys,
        len(_hashes),
        _hash_key("testkey123")[:16],
        _hash_key("testkey123") in _hashes,
    )

    if settings.run_migrations:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    yield
    await engine.dispose()


app = FastAPI(
    title="GeoHealth Context API",
    version="0.1.0",
    summary="Census-tract-level geographic health intelligence",
    description=_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    contact={
        "name": "GeoHealth API",
        "url": "https://github.com/RussellStover1983/geohealth-api",
    },
    license_info={"name": "MIT", "identifier": "MIT"},
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

app.include_router(context_router)
app.include_router(stats_router)
app.include_router(batch_router)
app.include_router(nearby_router)
app.include_router(compare_router)


@app.get(
    "/health",
    tags=["system"],
    summary="Health check",
    description="Check API and database connectivity. Returns 200 when "
    "healthy, 503 when the database is unreachable.",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse, "description": "Database unreachable"}},
)
async def health(session: AsyncSession = Depends(get_db)):
    """Check API and database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        total = metrics.cache_hits + metrics.cache_misses
        hit_rate = round(metrics.cache_hits / total, 4) if total else 0.0
        return {
            "status": "ok",
            "database": "connected",
            "cache": {
                "size": context_cache.size,
                "max_size": settings.cache_maxsize,
                "hit_rate": hit_rate,
            },
            "rate_limiter": {
                "active_keys": len(rate_limiter._buckets),
            },
            "uptime_seconds": metrics.uptime_seconds(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unreachable",
                "detail": str(exc),
            },
        )


@app.get(
    "/metrics",
    tags=["system"],
    summary="Application metrics",
    description="Returns application metrics including request counters, "
    "latency percentiles, cache stats, and geocoder/narrative success rates.",
)
async def get_metrics():
    """Return application metrics snapshot."""
    snap = metrics.snapshot()
    snap["cache"]["size"] = context_cache.size
    snap["cache"]["max_size"] = settings.cache_maxsize
    snap["rate_limiter"] = {"active_keys": len(rate_limiter._buckets)}
    return snap
