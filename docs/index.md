# GeoHealth Context API

Census-tract-level geographic health intelligence for the United States. Given a street address or lat/lng coordinates, returns **demographics**, **CDC Social Vulnerability Index (SVI) themes**, **CDC PLACES health outcome measures**, and an optional **AI-generated clinical narrative** for the surrounding census tract.

---

## Why This Matters

Social determinants of health (SDOH) — poverty, insurance status, housing, environmental factors — explain **up to 80% of health outcomes**. Yet most clinical systems lack structured access to neighborhood-level SDOH data.

GeoHealth bridges that gap. Every US census tract (~4,000 people) has a profile built from three federal data sources:

| Source | What It Provides |
|--------|-----------------|
| **American Community Survey (ACS)** | Demographics: population, income, poverty, insurance, unemployment, age |
| **CDC/ATSDR Social Vulnerability Index** | 4 vulnerability theme percentiles + overall composite |
| **CDC PLACES** | 14 health outcome prevalence measures (diabetes, obesity, mental health, etc.) |
| **Computed** | Composite SDOH index (0–1) for single-number clinical triage |

Plus an optional **AI-generated narrative** (powered by Anthropic Claude) that summarizes the clinical picture in plain language.

## Use Cases

- **Clinical risk models** — Enrich patient records with neighborhood-level SDOH factors
- **Patient intake workflows** — Flag social vulnerability during registration
- **Population health dashboards** — Visualize geographic health disparities across service areas
- **Research cohort enrichment** — Add standardized SDOH measures to study populations
- **Care coordination** — Identify patients from high-vulnerability tracts for proactive outreach

## Quick Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/context?address=1234+Main+St,+Minneapolis,+MN+55401"
```

Returns demographics, SVI themes, PLACES health outcomes, and a composite SDOH index — all in a single JSON response.

## What's in the Docs

- [**Quick Start**](quickstart.md) — Get an API key, make your first call, understand the response
- [**API Reference**](api-reference.md) — All endpoints with parameters, examples, and response shapes
- [**Data Dictionary**](data-dictionary.md) — 26 fields with clinical thresholds and interpretation guidance
- [**Python SDK & MCP**](sdk.md) — Typed Python client and AI agent integration

## Links

- **Live API**: [geohealth-api-production.up.railway.app](https://geohealth-api-production.up.railway.app/health)
- **Swagger UI**: [/docs](https://geohealth-api-production.up.railway.app/docs)
- **OpenAPI spec**: [/openapi.json](https://geohealth-api-production.up.railway.app/openapi.json)
- **PyPI**: [geohealth-api](https://pypi.org/project/geohealth-api/)
- **GitHub**: [RussellStover1983/geohealth-api](https://github.com/RussellStover1983/geohealth-api)
