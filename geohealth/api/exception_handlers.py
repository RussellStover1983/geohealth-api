"""Global exception handlers for structured JSON error responses."""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("geohealth.errors")


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Return structured JSON for all HTTP exceptions (4xx/5xx).

    Preserves ``X-RateLimit-*`` headers from 429 responses so clients can
    inspect their quota even on rate-limited requests.
    """
    headers = {}
    if exc.headers:
        headers = {
            k: v for k, v in exc.headers.items() if k.startswith("X-RateLimit-")
        }

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return structured JSON for request validation errors (422)."""
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "status_code": 422,
            "detail": exc.errors(),
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unhandled exceptions.

    Logs the full traceback server-side but returns a generic 500 response
    with no internal details leaked.
    """
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
