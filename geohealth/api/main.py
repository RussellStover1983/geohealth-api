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

logger = logging.getLogger("geohealth")


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    description="Census-tract-level geographic health intelligence",
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
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def health(session: AsyncSession = Depends(get_db)):
    """Check API and database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unreachable",
                "detail": str(exc),
            },
        )
