from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from geohealth.api.routes.context import router as context_router
from geohealth.config import settings
from geohealth.db.models import Base
from geohealth.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (no Alembic in Phase 1)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="GeoHealth Context API",
    version="0.1.0",
    description="Census-tract-level geographic health intelligence",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(context_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
