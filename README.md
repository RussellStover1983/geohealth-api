# GeoHealth Context API

Census-tract-level geographic health intelligence API. Given a street address or lat/lng coordinates, returns **demographics**, **CDC/ATSDR Social Vulnerability Index (SVI) themes**, **CDC PLACES health outcome measures**, and an optional **AI-generated narrative** for the surrounding census tract.

## Features

- Address and coordinate geocoding (Census Bureau + Nominatim fallback)
- Census tract resolution via PostGIS spatial queries or FIPS-code lookup
- ACS demographics: population, income, poverty, insurance, unemployment, age
- CDC/ATSDR SVI theme percentile rankings (4 themes)
- CDC PLACES health outcome measures (crude prevalence)
- Composite SDOH index
- AI-generated narrative summaries (Anthropic Claude)
- Batch address lookups, spatial radius search, tract comparison
- Per-key sliding-window rate limiting with standard headers
- SHA-256 API key hashing

## Quick Start

### 1. Clone and start services

```bash
git clone https://github.com/RussellStover1983/geohealth-api.git
cd geohealth-api
docker compose up --build -d
```

This launches PostgreSQL/PostGIS and the API on `http://localhost:8000`.

### 2. Load census tract data

```bash
# Single state (fast, good for development)
pip install -e ".[etl]"
python -m geohealth.etl.load_all --state 27

# All states (resumable)
python -m geohealth.etl.load_all --state all --resume
```

### 3. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"connected","detail":null}
```

## Interactive API Docs

Once running, explore the full API interactively:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## Authentication

Most endpoints require an API key via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-key-here" "http://localhost:8000/v1/context?address=..."
```

**Configuration:**

| Variable | Description |
|----------|-------------|
| `AUTH_ENABLED` | Set to `true` to enforce key validation (default: `false`) |
| `API_KEYS` | Comma-separated list of valid keys |

Keys can be provided as plaintext or as pre-hashed SHA-256 hex strings. The API always hashes keys with SHA-256 before comparison — plaintext keys are never stored or logged.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | API and database connectivity check |
| GET | `/v1/context` | Yes | Primary lookup — address or lat/lng to tract data |
| POST | `/v1/batch` | Yes | Batch address lookup (up to `BATCH_MAX_SIZE`) |
| GET | `/v1/nearby` | Yes | Find census tracts within a radius |
| GET | `/v1/compare` | Yes | Compare two tracts or tract vs. averages |
| GET | `/v1/stats` | Yes | Per-state data loading statistics |
| GET | `/metrics` | No | Application metrics (counters, latency, cache stats) |

## Example Requests

### Context lookup by address

```bash
curl -H "X-API-Key: test" \
  "http://localhost:8000/v1/context?address=1234+Main+St,+Minneapolis,+MN+55401"
```

### Context lookup by coordinates with narrative

```bash
curl -H "X-API-Key: test" \
  "http://localhost:8000/v1/context?lat=44.9778&lng=-93.265&narrative=true"
```

### Batch lookup

```bash
curl -X POST -H "X-API-Key: test" -H "Content-Type: application/json" \
  -d '{"addresses":["1234 Main St, Minneapolis, MN","456 Oak Ave, St Paul, MN"]}' \
  http://localhost:8000/v1/batch
```

### Nearby tracts

```bash
curl -H "X-API-Key: test" \
  "http://localhost:8000/v1/nearby?lat=44.9778&lng=-93.265&radius=5&limit=10"
```

### Compare tracts

```bash
# Two tracts
curl -H "X-API-Key: test" \
  "http://localhost:8000/v1/compare?geoid1=27053026200&geoid2=27053026300"

# Tract vs. state average
curl -H "X-API-Key: test" \
  "http://localhost:8000/v1/compare?geoid1=27053026200&compare_to=state"
```

### Statistics

```bash
curl -H "X-API-Key: test" "http://localhost:8000/v1/stats"
```

## Python SDK

The project includes a typed Python SDK that wraps every endpoint with both async and sync clients.

### Async usage

```python
from geohealth.sdk import AsyncGeoHealthClient

async with AsyncGeoHealthClient("http://localhost:8000", api_key="your-key") as client:
    result = await client.context(address="1234 Main St, Minneapolis, MN 55401")
    print(result.tract.geoid, result.tract.poverty_rate)

    nearby = await client.nearby(lat=44.9778, lng=-93.265, radius=3.0)
    for tract in nearby.tracts:
        print(tract.geoid, tract.distance_miles)
```

### Sync usage

```python
from geohealth.sdk import GeoHealthClient

with GeoHealthClient("http://localhost:8000", api_key="your-key") as client:
    result = client.context(lat=44.9778, lng=-93.265)
    print(result.tract.geoid)
```

### Error handling

```python
from geohealth.sdk import AsyncGeoHealthClient, RateLimitError, AuthenticationError

async with AsyncGeoHealthClient("http://localhost:8000", api_key="your-key") as client:
    try:
        result = await client.context(address="123 Main St")
    except RateLimitError as exc:
        print(f"Rate limited! Resets in {exc.rate_limit_info.reset}s")
    except AuthenticationError as exc:
        print(f"Auth failed: {exc.detail}")
```

## Rate Limiting

Every authenticated response includes rate-limit headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Seconds until the window resets |

When the limit is exceeded, the API returns `429 Too Many Requests` with the same headers. Configure via `RATE_LIMIT_PER_MINUTE` (default: 60).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `AUTH_ENABLED` | `false` | Enable API key authentication |
| `API_KEYS` | — | Comma-separated valid keys (plaintext or SHA-256 hex) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per key per minute |
| `ANTHROPIC_API_KEY` | — | Anthropic API key for narrative generation |
| `BATCH_MAX_SIZE` | `50` | Maximum addresses per batch request |
| `CACHE_MAXSIZE` | `4096` | LRU cache maximum entries |
| `CACHE_TTL` | `3600` | Cache time-to-live in seconds |
| `RUN_MIGRATIONS` | `true` | Run Alembic migrations on startup |
| `LOG_FORMAT` | `text` | `text` for human-readable, `json` for structured JSON |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |

## Observability

### Structured Logging

The API supports two log formats controlled by `LOG_FORMAT`:

- **`text`** (default) — Human-readable format with optional request ID prefix: `2024-01-15 12:00:00 INFO     [abcdef123456] geohealth.access - GET /health 200 1.23ms`
- **`json`** — Single-line JSON for log aggregators with `timestamp`, `level`, `logger`, `message`, `request_id`, and optional `exception` fields

### Request Correlation

Every request gets an `X-Request-ID` header. If the client sends one, it is echoed back; otherwise a new UUID is generated. The request ID is included in all log lines and is available to downstream services for distributed tracing.

### Application Metrics

`GET /metrics` returns a JSON snapshot of application metrics:

- **Request counters** — total requests, status code breakdown
- **Cache stats** — hits, misses, hit rate, current size
- **Geocoder stats** — Census/Nominatim success and failure counts
- **Narrative stats** — success and failure counts
- **Latency percentiles** — p50, p90, p95, p99

### Enhanced Health Check

`GET /health` now includes cache, rate limiter, and uptime information when the database is healthy.

## Deployment (Railway)

The API is configured for deployment on [Railway](https://railway.app) using the existing multi-stage Dockerfile.

### Prerequisites

- A [Railway](https://railway.app) account
- The GitHub repo linked to your Railway project

### 1. Create a Railway project

1. In the Railway dashboard, click **New Project** → **Deploy from GitHub Repo**
2. Select the `geohealth-api` repository
3. Railway will detect the `railway.toml` and build from the Dockerfile automatically

### 2. Add a PostGIS database service

Railway's managed Postgres does not include PostGIS binaries, so add a **custom Docker service**:

1. In your Railway project, click **New** → **Docker Image**
2. Set the image to `postgis/postgis:16-3.4`
3. Add a **persistent volume** mounted at `/var/lib/postgresql/data`
4. Add these environment variables to the PostGIS service:
   - `POSTGRES_USER=geohealth`
   - `POSTGRES_PASSWORD=<strong-password>`
   - `POSTGRES_DB=geohealth`
5. Note the service's internal hostname (e.g., `postgis.railway.internal`) and port

### 3. Configure environment variables on the API service

Set these variables on the **API service** (not the PostGIS service):

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://geohealth:<password>@${{PostGIS.RAILWAY_PRIVATE_DOMAIN}}:5432/geohealth` |
| `DATABASE_URL_SYNC` | `postgresql://geohealth:<password>@${{PostGIS.RAILWAY_PRIVATE_DOMAIN}}:5432/geohealth` |
| `AUTH_ENABLED` | `true` |
| `API_KEYS` | Comma-separated SHA-256 hashes (see step 6) |
| `CORS_ORIGINS` | Your frontend domain(s), e.g., `https://app.example.com` |
| `LOG_FORMAT` | `json` |
| `ANTHROPIC_API_KEY` | *(optional)* Your Anthropic key for AI narrative generation |

### 4. Deploy and verify

Railway auto-deploys on push to `master`. After the build completes:

```bash
curl https://<your-app>.railway.app/health
# {"status":"ok","database":"connected","detail":null}
```

### 5. Load census data

Run the ETL from your local machine against Railway's **public** database URL (found in the PostGIS service's networking settings):

```bash
pip install -e ".[etl]"
DATABASE_URL_SYNC=postgresql://geohealth:<password>@<public-host>:<port>/geohealth \
  python -m geohealth.etl.load_all --state 27
```

For all states (resumable):

```bash
DATABASE_URL_SYNC=postgresql://geohealth:<password>@<public-host>:<port>/geohealth \
  python -m geohealth.etl.load_all --state all --resume
```

### 6. Generate and distribute API keys

Generate a random key and its SHA-256 hash:

```bash
python -c "
import secrets, hashlib
key = secrets.token_urlsafe(32)
hashed = hashlib.sha256(key.encode()).hexdigest()
print(f'Give to client: {key}')
print(f'Add to API_KEYS: {hashed}')
"
```

Add the hash to `API_KEYS` in Railway's environment variables (comma-separated if multiple). Distribute the plaintext key to the API consumer — the API never stores or logs it.

## Development

### Local setup

```bash
pip install -e ".[dev]"           # Core + test deps
pip install -e ".[dev,etl]"       # Include ETL deps (geopandas, shapely, etc.)
```

### Run the dev server

```bash
docker compose up -d db           # Start PostGIS only
uvicorn geohealth.api.main:app --reload
```

### Tests

```bash
pytest                             # All tests (no live DB required)
pytest tests/test_context.py -v    # Single module
pytest -k test_auth                # Pattern match
```

### Lint

```bash
ruff check geohealth/ tests/      # line-length=99, target py311
```

### Migrations

```bash
alembic upgrade head                                  # Apply all
alembic revision --autogenerate -m "description"      # Generate new
alembic stamp head                                    # Mark existing DB as current
```

## Project Structure

```
geohealth/
├── api/            # FastAPI app, routes, schemas, middleware, auth
│   └── routes/     # Endpoint modules (context, batch, nearby, compare, stats)
├── services/       # Geocoding, tract lookup, cache, rate limiter, narrator
├── etl/            # Data loading (TIGER/Line, ACS, SVI, PLACES)
├── db/             # SQLAlchemy models and async session
├── migrations/     # Alembic migration versions
└── config.py       # Settings via pydantic-settings
```

## License

MIT
