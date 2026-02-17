# GeoHealth Context API

Census-tract-level geographic health intelligence API. Given an address or coordinates, returns social determinants of health (SDOH) data, CDC/ATSDR Social Vulnerability Index (SVI) themes, and CDC PLACES health measures.

## Quick Start

### 1. Start services

```bash
docker-compose up -d
```

This launches PostGIS and the API on `http://localhost:8000`.

### 2. Load census tract geometries

```bash
# Single state (fast, good for dev)
python -m geohealth.etl.load_tiger --year 2022 --state 27

# All states
python -m geohealth.etl.load_tiger --year 2022 --state all
```

### 3. Query the API

```bash
# Health check
curl http://localhost:8000/health

# By address
curl "http://localhost:8000/v1/context?address=1234+Main+St,+Minneapolis,+MN+55401"

# By coordinates
curl "http://localhost:8000/v1/context?lat=44.9778&lng=-93.265"
```

## Development

```bash
pip install -e ".[dev,etl]"
pytest
```

## Project Structure

```
geohealth/
├── api/          # FastAPI app, routes, dependencies
├── services/     # Geocoding, tract lookup
├── etl/          # TIGER/Line shapefile loader
├── db/           # SQLAlchemy models, session
└── config.py     # Settings (env vars)
```

## License

MIT
