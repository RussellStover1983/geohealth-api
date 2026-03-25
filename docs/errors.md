# Error Handling

## Error Response Format

All non-2xx responses return a consistent JSON structure:

```json
{
  "error": true,
  "status_code": 400,
  "detail": "Provide either 'address' or both 'lat' and 'lng'."
}
```

The `detail` field is always a string for HTTP errors. The only exception is **422 Validation Error**, where `detail` is a list of objects (see below).

---

## HTTP Status Codes

### 400 Bad Request

Invalid input that the server cannot process.

| `detail` | Endpoint | Cause | Fix |
|----------|----------|-------|-----|
| `"Provide either 'address' or both 'lat' and 'lng'."` | GET /v1/context | Neither address nor coordinates provided | Supply `address` OR both `lat` and `lng` |
| `"Too many addresses: N exceeds max of 50"` | POST /v1/batch | Batch size exceeded | Split into multiple requests of 50 or fewer |
| `"Provide either 'geoid2' or 'compare_to', not both."` | GET /v1/compare | Ambiguous comparison target | Use one or the other |
| `"Provide either 'geoid2' or 'compare_to'."` | GET /v1/compare | Neither comparison target given | Supply `geoid2` for tract-to-tract or `compare_to` for averages |
| `"'compare_to' must be 'county', 'state', or 'national'."` | GET /v1/compare | Invalid comparison scope | Use one of the three valid values |
| `"Invalid event types: ..."` | POST /v1/webhooks | Unrecognized webhook event type | Use `data.updated` or `threshold.exceeded` |
| `"Maximum 10 active webhooks per API key."` | POST /v1/webhooks | Webhook limit reached | Delete unused webhooks first |
| `"Invalid category '...'. Valid: demographics, vulnerability, health_outcomes, environmental, composite, identity"` | GET /v1/dictionary | Bad category filter | Use a valid category name |

### 401 Unauthorized

```json
{
  "error": true,
  "status_code": 401,
  "detail": "Missing API key"
}
```

**Cause:** No `X-API-Key` header was sent with the request.

**Fix:** Add the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/context?address=..."
```

### 403 Forbidden

```json
{
  "error": true,
  "status_code": 403,
  "detail": "Invalid API key"
}
```

**Cause:** The provided key does not match any configured key (SHA-256 hash comparison).

**Fix:** Verify your key is correct. Contact the project maintainer for a new key if needed.

### 404 Not Found

| `detail` | Endpoint | Cause |
|----------|----------|-------|
| `"Tract {geoid} not found."` | GET /v1/compare, /v1/trends, /v1/demographics/compare | GEOID does not exist in loaded data |
| `"No census tract found for this location"` | GET /v1/context | Location is outside loaded states |
| `"Webhook not found."` | DELETE /v1/webhooks/{id} | Webhook ID does not exist or belongs to another key |

**Fix:** Check which states have data loaded via `GET /v1/stats`. Currently loaded: GA (13), KS (20), MN (27), MO (29).

### 422 Validation Error

Returned when request parameters fail Pydantic v2 validation. This is the **only** error where `detail` is not a string — it is a list of validation error objects.

```json
{
  "error": true,
  "status_code": 422,
  "detail": [
    {
      "loc": ["query", "lat"],
      "msg": "Input should be a valid number",
      "type": "float_parsing"
    }
  ]
}
```

Each object in the `detail` list contains:

| Field | Description |
|-------|-------------|
| `loc` | Path to the invalid field (e.g., `["query", "lat"]`, `["body", "addresses"]`) |
| `msg` | Human-readable error message |
| `type` | Pydantic error type identifier |

### 429 Rate Limited

```json
{
  "error": true,
  "status_code": 429,
  "detail": "Rate limit exceeded"
}
```

The response includes rate-limit headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests per window (default: 60) |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Seconds until the window resets |

#### Handling 429s

Use exponential backoff to avoid hammering the server:

```python
import time
import httpx

def request_with_backoff(url: str, headers: dict, max_retries: int = 3):
    for attempt in range(max_retries):
        resp = httpx.get(url, headers=headers)
        if resp.status_code != 429:
            return resp
        reset = int(resp.headers.get("X-RateLimit-Reset", 1))
        wait = min(reset, 2 ** attempt)
        time.sleep(wait)
    return resp
```

### 500 Internal Server Error

```json
{
  "error": true,
  "status_code": 500,
  "detail": "Internal server error"
}
```

**Cause:** An unexpected server error occurred. No internal details are leaked.

**Fix:** Retry the request. If the error persists, check `GET /health` to verify API and database status.

---

## Error Handling in the Python SDK

The SDK maps each HTTP status to a typed exception:

| HTTP Status | SDK Exception | When |
|-------------|---------------|------|
| 401 | `AuthenticationError` | Missing API key |
| 403 | `AuthenticationError` | Invalid API key |
| 404 | `NotFoundError` | Tract or webhook not found |
| 422 | `ValidationError` | Invalid request parameters |
| 429 | `RateLimitError` | Rate limit exceeded |

### Catching errors

```python
from geohealth.sdk import (
    AsyncGeoHealthClient,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

async with AsyncGeoHealthClient(
    "https://geohealth-api-production.up.railway.app",
    api_key="your-key",
) as client:
    try:
        result = await client.context(address="123 Main St")
    except AuthenticationError as exc:
        # 401 or 403 — bad or missing API key
        print(f"Auth failed: {exc.detail}")
    except NotFoundError:
        # 404 — no census tract found for this location
        print("Location is outside loaded states")
    except ValidationError as exc:
        # 422 — invalid parameters
        print(f"Invalid request: {exc.detail}")
    except RateLimitError as exc:
        # 429 — back off and retry
        print(f"Rate limited! Resets in {exc.rate_limit_info.reset}s")
```
