"""DPC Market Fit API — FastAPI application entry point."""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers.competition import router as competition_router
from app.routers.demand import router as demand_router
from app.routers.employer import router as employer_router
from app.routers.market_fit import router as market_fit_router
from app.routers.supply import router as supply_router

logger = logging.getLogger("dpc_market_fit")

_DESCRIPTION = """\
Evaluate the geographic market viability for Direct Primary Care (DPC) practices.

Given a location (address, lat/lon, ZIP code, or census tract FIPS), the API:
1. Resolves to census tract(s) within a configurable radius
2. Assembles data from Census ACS, CDC PLACES, and CDC SVI
3. Returns a composite **DPC Market Fit Score** (0-100) with five dimensional sub-scores:
   **Demand**, **Supply Gap**, **Affordability**, **Employer Opportunity**, and **Competition**

### Phase 1 (Current)
- Demand and Affordability dimensions are fully scored from live data
- Supply Gap, Employer, and Competition return placeholder scores pending Phase 2-3 data integration

### Score Categories
| Range | Category |
|-------|----------|
| 80-100 | EXCELLENT |
| 60-79 | STRONG |
| 40-59 | MODERATE |
| 0-39 | WEAK |
"""

_OPENAPI_TAGS = [
    {
        "name": "market-fit",
        "description": "Primary DPC Market Fit scoring endpoint.",
    },
    {
        "name": "demand",
        "description": "Detailed demand-side indicators.",
    },
    {
        "name": "supply",
        "description": "Provider supply analysis (Phase 2).",
    },
    {
        "name": "employer",
        "description": "Employer landscape analysis (Phase 3).",
    },
    {
        "name": "competition",
        "description": "Competition/saturation analysis (Phase 3).",
    },
    {
        "name": "system",
        "description": "Health checks and operational endpoints.",
    },
]

app = FastAPI(
    title="DPC Market Fit API",
    version="0.1.0",
    summary="Geographic market viability scoring for Direct Primary Care practices",
    description=_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    license_info={"name": "MIT", "identifier": "MIT"},
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "status_code": 422,
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "Internal server error",
        },
    )


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(market_fit_router)
app.include_router(demand_router)
app.include_router(supply_router)
app.include_router(employer_router)
app.include_router(competition_router)


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["system"], summary="Health check")
async def health() -> dict:
    return {"status": "ok", "version": app.version}
