# NPI Provider Map Layer — Autonomous Execution Plan

## Objective

Add individual NPI provider pins to the GeoHealth map. Users can see where PCPs are geographically located, click a pin to see provider details (name, taxonomy, address, FQHC flag), and filter by provider type. This is the foundation for a future "reference network" feature.

---

## Data Source

NPPES February 2026 release is pre-downloaded at `C:\dev\nppes\`:
- `npidata_pfile_20050523-20260208.csv` — 9.37M rows (already extracted, no download needed)
- `pl_pfile_20050523-20260208.csv` — 1.15M secondary practice locations

Taxonomy config: `dpc-market-fit/app/data/npi_taxonomy_config.json` (tier1/tier2 PCP codes + facility codes including FQHC=261QF0400X)

Target states: GA (13), KS (20), MN (27), MO (29) — matching loaded tract data.

---

## Step 1: Database Model

**File to modify**: `geohealth/db/models.py`

Add `NpiProvider` model with these columns:

| Column | Type | Notes |
|--------|------|-------|
| `npi` (PK) | String(10) | National Provider Identifier |
| `entity_type` | String(1) | 1=individual, 2=organization |
| `provider_name` | Text | Full name or org name |
| `credential` | String(50) | MD, DO, NP, PA, etc. |
| `gender` | String(1) | M/F/null |
| `primary_taxonomy` | String(15) | e.g., 207Q00000X |
| `taxonomy_description` | Text | e.g., "Family Medicine" |
| `provider_type` | String(30) | pcp, fqhc, urgent_care, rural_health_clinic, etc. |
| `practice_address` | Text | Street address |
| `practice_city` | String(100) | |
| `practice_state` | String(2) | |
| `practice_zip` | String(5) | |
| `phone` | String(20) | |
| `is_fqhc` | Boolean | True if any taxonomy = 261QF0400X |
| `tract_fips` | String(11) | From Census geocoder |
| `geom` | Geometry(POINT, 4326) | PostGIS point, GiST-indexed |

Indexes: GiST on `geom`, btree on `practice_state`, `provider_type`, `tract_fips`.

Then generate Alembic migration: `alembic revision --autogenerate -m "add npi_providers table"`

---

## Step 2: ETL Pipeline

**New file**: `geohealth/etl/load_npi_providers.py`

Read directly from `C:\dev\nppes\npidata_pfile_20050523-20260208.csv` (no download needed).

### Logic:
1. Load taxonomy codes from `dpc-market-fit/app/data/npi_taxonomy_config.json` — build sets of tier1+tier2 PCP codes and facility codes
2. Stream CSV rows, filter to:
   - Practice state in {GA, KS, MN, MO}
   - At least one taxonomy code (columns `Healthcare Provider Taxonomy Code_1` through `_15`) matching PCP or facility codes
   - No deactivation date set (`NPI Deactivation Date` is empty)
3. Extract per provider:
   - NPI, entity_type, name (first+last for individuals, org name for orgs), credential, gender
   - Primary taxonomy code (the one with `Healthcare Provider Primary Taxonomy Switch_N` = "Y")
   - Look up taxonomy_description from config
   - Classify provider_type: check all taxonomy codes against facility_codes for FQHC/urgent_care/etc., else "pcp"
   - Set `is_fqhc = True` if any taxonomy code = `261QF0400X`
   - Practice address fields: street, city, state, zip (first 5 digits), phone
4. Batch geocode via Census Bureau batch geocoder:
   - POST to `https://geocoding.geo.census.gov/geocoder/geographies/addressbatch`
   - Send 1000 addresses per batch (Census limit is 10K but smaller batches are more reliable)
   - Response includes lat, lon, and tract FIPS
   - For failures, try Nominatim fallback (rate limit 1 req/sec)
5. Build PostGIS geometry: `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`
6. Bulk upsert into `npi_providers` table (use NPI as conflict key)
7. Print progress: number of providers processed, geocoded, failed

### CLI interface:
```bash
python -m geohealth.etl.load_npi_providers \
    --nppes-csv "C:\dev\nppes\npidata_pfile_20050523-20260208.csv" \
    --states GA,KS,MN,MO
```

Expected output: ~30,000-60,000 providers for 4 states.

### Important: Geocoding takes time
The Census batch geocoder is free but not instant. Budget ~30-60 minutes for all providers across 4 states. The ETL should:
- Save progress (checkpoint after each batch)
- Support `--resume` flag to continue from last checkpoint
- Log failed geocodes to a separate file for review

---

## Step 3: Backend API

**New file**: `geohealth/api/routes/providers.py`

### Endpoint 1: `GET /v1/providers/geojson`
For map rendering. Returns GeoJSON FeatureCollection of Point features.

**Parameters**:
- `bbox` (required): `west,south,east,north` as comma-separated floats
- `provider_type` (optional): `all` | `pcp` | `fqhc` | `urgent_care` | `rural_health_clinic` (default: `all`)
- `limit` (optional): max 2000, default 500

**PostGIS query**: `WHERE geom && ST_MakeEnvelope(west, south, east, north, 4326)` using GiST index.

**Response**: `Content-Type: application/geo+json`
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [-94.58, 39.11]},
      "properties": {
        "npi": "1234567890",
        "provider_name": "Dr. Jane Smith",
        "credential": "MD",
        "primary_taxonomy": "207Q00000X",
        "taxonomy_description": "Family Medicine",
        "provider_type": "pcp",
        "practice_address": "123 Main St",
        "practice_city": "Kansas City",
        "practice_state": "MO",
        "practice_zip": "64108",
        "phone": "8165551234",
        "is_fqhc": false,
        "entity_type": "1"
      }
    }
  ]
}
```

### Endpoint 2: `GET /v1/providers`
For programmatic use and future reference network.

**Parameters**:
- `lat` + `lng` + `radius` (miles, default 5, max 50) — radius search
- OR `tract_fips` — providers in a specific tract
- `provider_type` (optional, default `all`)
- `limit` (default 50, max 500) + `offset` (default 0)

**Response**:
```json
{
  "count": 25,
  "total": 142,
  "offset": 0,
  "limit": 50,
  "providers": [
    {
      "npi": "1234567890",
      "provider_name": "Dr. Jane Smith",
      "credential": "MD",
      "primary_taxonomy": "207Q00000X",
      "taxonomy_description": "Family Medicine",
      "provider_type": "pcp",
      "practice_address": "123 Main St",
      "practice_city": "Kansas City",
      "practice_state": "MO",
      "practice_zip": "64108",
      "phone": "8165551234",
      "is_fqhc": false,
      "entity_type": "1",
      "gender": "F",
      "tract_fips": "29095015200",
      "lat": 39.111,
      "lng": -94.583,
      "distance_miles": 1.2
    }
  ]
}
```

### Pydantic schemas to add in `geohealth/api/schemas.py`:
- `ProviderModel` — single provider
- `ProvidersResponse` — paginated list wrapper

### Register in `geohealth/api/main.py`:
```python
from geohealth.api.routes.providers import router as providers_router
app.include_router(providers_router)
```

### Tests:
Write tests in `tests/test_providers.py` following existing mock patterns (AsyncMock for DB session, no live DB). Test:
- GeoJSON bbox endpoint returns FeatureCollection
- Radius search returns providers sorted by distance
- Tract FIPS filter works
- Provider type filter works
- Limit/offset pagination
- Empty results
- Invalid bbox format returns 422

---

## Step 4: Frontend Types + API Client

### `geohealth-ui/lib/api/types.ts` — add:
```typescript
export interface NpiProvider {
  npi: string;
  entity_type: string;
  provider_name: string;
  credential: string | null;
  gender: string | null;
  primary_taxonomy: string;
  taxonomy_description: string | null;
  provider_type: string;
  practice_address: string | null;
  practice_city: string | null;
  practice_state: string;
  practice_zip: string | null;
  phone: string | null;
  is_fqhc: boolean;
  tract_fips: string | null;
  lat: number | null;
  lng: number | null;
  distance_miles?: number;
}

export interface ProvidersResponse {
  count: number;
  total: number;
  offset: number;
  limit: number;
  providers: NpiProvider[];
}
```

### `geohealth-ui/lib/api/client.ts` — add methods:
- `getProvidersGeoJSON(bbox, providerType?, limit?)` → fetches `/v1/providers/geojson`
- `getProviders(params)` → fetches `/v1/providers`

### `geohealth-ui/lib/api/hooks.ts` — add hook:
- `useProvidersGeoJSON(bbox, providerType, enabled)` — SWR-style hook that fetches on viewport change

---

## Step 5: Zustand Store Updates

**File**: `geohealth-ui/lib/store.ts`

Add to the store:
```typescript
showProviders: boolean;           // toggle provider layer visibility
setShowProviders: (show: boolean) => void;
providerFilter: string;           // "all" | "pcp" | "fqhc" | "urgent_care" | ...
setProviderFilter: (filter: string) => void;
selectedProvider: NpiProvider | null;  // clicked provider for popup
setSelectedProvider: (provider: NpiProvider | null) => void;
```

---

## Step 6: Map Layer — Clustered Provider Points

**File**: `geohealth-ui/components/map/MapContainer.tsx`

### Add provider data loading:
- When `showProviders` is true AND zoom >= 9, fetch providers for current viewport bbox
- Debounce 300ms (same pattern as tract loading)
- Get bbox from `mapRef.current.getMap().getBounds()`

### Add MapLibre Source + Layers:
```tsx
<Source
  id="npi-providers"
  type="geojson"
  data={providersGeoJSON}
  cluster={true}
  clusterMaxZoom={14}
  clusterRadius={50}
>
  {/* Cluster circles — sized by count */}
  <Layer id="provider-clusters" type="circle"
    filter={["has", "point_count"]}
    paint={{
      "circle-color": ["step", ["get", "point_count"],
        "#51bbd6", 10, "#f1f075", 50, "#f28cb1"],
      "circle-radius": ["step", ["get", "point_count"],
        15, 10, 20, 50, 25],
    }}
  />
  {/* Cluster count labels */}
  <Layer id="provider-cluster-count" type="symbol"
    filter={["has", "point_count"]}
    layout={{ "text-field": ["get", "point_count_abbreviated"], "text-size": 12 }}
  />
  {/* Individual provider points */}
  <Layer id="provider-point" type="circle"
    filter={["!", ["has", "point_count"]]}
    paint={{
      "circle-color": ["case", ["get", "is_fqhc"], "#E11D48", "#2563EB"],
      "circle-radius": 6,
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff",
    }}
  />
</Source>
```

### Click handler:
- Extend existing `onClick` to check for clicks on `provider-point` layer → set `selectedProvider`
- Clicks on `provider-clusters` → zoom to expand (use `getClusterExpansionZoom`)

---

## Step 7: Provider Popup

**New file**: `geohealth-ui/components/map/ProviderPopup.tsx`

MapLibre `<Popup>` component, shown when `selectedProvider` is set:

```
┌──────────────────────────────────┐
│ Dr. Jane Smith, MD          [x] │
│ Family Medicine (207Q00000X)    │
│ ─────────────────────────────── │
│ 123 Main St                     │
│ Kansas City, MO 64108           │
│ (816) 555-1234  ← clickable    │
│ ─────────────────────────────── │
│ [FQHC badge if applicable]     │
│ NPI: 1234567890                 │
│ Tract: 29095001200              │
└──────────────────────────────────┘
```

- Blue styling for regular providers, rose/red accent for FQHCs
- Organization name shown for entity_type=2
- Phone as clickable `tel:` link
- Close button clears `selectedProvider`

---

## Step 8: Layer Panel Toggle

**File**: `geohealth-ui/components/panels/LayerPanel.tsx`

Add a "Providers" section at the top (separate from choropleth metrics — this is a point overlay, not a fill layer):

```
[toggle switch] Show NPI Providers
  Filter: [All] [PCPs] [FQHCs] [Urgent Care] [Rural Health]
```

Toggle controls `showProviders` in store. Filter buttons control `providerFilter`.

---

## Step 9: Documentation

- Update `docs/api-reference.md` with the two new endpoints
- Update `docs/data-dictionary.md` with `npi_providers` table
- Update `geohealth-ui/.env.local.example` if any new env vars needed (unlikely)

---

## Step 10: Testing + Lint + Build

1. `pytest` — all existing 192 tests + new provider tests pass
2. `ruff check geohealth/ tests/` — clean
3. `pnpm build` in `geohealth-ui/` — succeeds
4. Fix any failures before proceeding

---

## Step 11: Load Data

Run the ETL against Railway PostGIS (requires TCP proxy to be enabled):
```bash
python -m geohealth.etl.load_npi_providers \
    --nppes-csv "C:\dev\nppes\npidata_pfile_20050523-20260208.csv" \
    --states GA,KS,MN,MO
```

**Note**: You will need the Railway PostGIS TCP proxy enabled for this step. The user may need to enable it in the Railway dashboard first. If the connection fails, print instructions for enabling the TCP proxy and exit gracefully.

---

## Step 12: Deploy

1. Push code to `origin/master`
2. Railway auto-deploys the backend (runs `alembic upgrade head` on startup)
3. Vercel auto-deploys the frontend from master
4. Verify: visit https://geohealth-api.vercel.app, search an address, zoom to 9+, confirm provider pins appear

---

## Key Files Reference

| File | Action |
|------|--------|
| `geohealth/db/models.py` | Add `NpiProvider` model |
| `geohealth/etl/load_npi_providers.py` | **New** — ETL pipeline |
| `geohealth/api/routes/providers.py` | **New** — API endpoints |
| `geohealth/api/schemas.py` | Add `ProviderModel`, `ProvidersResponse` |
| `geohealth/api/main.py` | Register providers router |
| `tests/test_providers.py` | **New** — backend tests |
| `docs/api-reference.md` | Add provider endpoints |
| `docs/data-dictionary.md` | Add npi_providers table |
| `geohealth-ui/lib/api/types.ts` | Add `NpiProvider`, `ProvidersResponse` |
| `geohealth-ui/lib/api/client.ts` | Add provider methods |
| `geohealth-ui/lib/api/hooks.ts` | Add `useProvidersGeoJSON` hook |
| `geohealth-ui/lib/store.ts` | Add provider state |
| `geohealth-ui/components/map/MapContainer.tsx` | Add provider layer + click handler |
| `geohealth-ui/components/map/ProviderPopup.tsx` | **New** — popup component |
| `geohealth-ui/components/panels/LayerPanel.tsx` | Add provider toggle + filter |

## Patterns to Follow

| Pattern | Reference File |
|---------|----------------|
| NPPES CSV parsing/filtering | `dpc-market-fit/etl/load_npi_tract.py` |
| Taxonomy code classification | `dpc-market-fit/app/data/npi_taxonomy_config.json` |
| PostGIS spatial queries | `geohealth/api/routes/geojson.py` |
| GeoJSON endpoint shape | `geohealth/api/routes/geojson.py` |
| Alembic migration | `geohealth/migrations/versions/` |
| API route + schema pattern | `geohealth/api/routes/nearby.py` + `schemas.py` |
| Backend test mocking | `tests/test_nearby.py` or `tests/test_geojson.py` |
| MapLibre Source/Layer | `geohealth-ui/components/map/MapContainer.tsx` (tract layers) |
| Zustand store pattern | `geohealth-ui/lib/store.ts` |
| API hooks pattern | `geohealth-ui/lib/api/hooks.ts` |

## Future: Reference Network

This design stores individual providers with unique NPI keys, setting up for:
- Future `reference_networks` table with FK to `npi_providers.npi`
- "Add to network" action from popup
- "Show only in-network" filter
- Network builder UI using `/v1/providers` endpoint
