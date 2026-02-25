# Python SDK & MCP Server

## Installation

```bash
# Core SDK
pip install geohealth-api

# With MCP server for AI agents
pip install geohealth-api[mcp]
```

---

## Python SDK

The SDK provides typed async and sync clients wrapping every API endpoint. Methods return Pydantic models with full type hints.

### Async client

```python
from geohealth.sdk import AsyncGeoHealthClient

async with AsyncGeoHealthClient(
    "https://geohealth-api-production.up.railway.app",
    api_key="your-key",
) as client:
    # Primary lookup
    result = await client.context(address="1234 Main St, Minneapolis, MN 55401")
    print(result.tract.geoid, result.tract.poverty_rate)
    print(result.tract.places_measures)  # dict of health outcomes

    # With AI narrative
    result = await client.context(lat=44.9778, lng=-93.265, narrative=True)
    print(result.narrative)

    # Nearby tracts
    nearby = await client.nearby(lat=44.9778, lng=-93.265, radius=3.0)
    for tract in nearby.tracts:
        print(tract.geoid, tract.distance_miles, tract.sdoh_index)

    # Compare tracts
    comparison = await client.compare(geoid1="27053026200", geoid2="27053026300")

    # Data dictionary
    dictionary = await client.dictionary()
    for cat in dictionary.categories:
        for field in cat.fields:
            print(f"{field.name}: {field.clinical_relevance}")

    # Batch lookup
    batch = await client.batch(addresses=[
        "1234 Main St, Minneapolis, MN",
        "456 Oak Ave, St Paul, MN",
    ])
```

### Sync client

For scripts and notebooks where async isn't needed:

```python
from geohealth.sdk import GeoHealthClient

with GeoHealthClient(
    "https://geohealth-api-production.up.railway.app",
    api_key="your-key",
) as client:
    result = client.context(lat=44.9778, lng=-93.265)
    print(result.tract.geoid)
```

### Error handling

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
    except RateLimitError as exc:
        print(f"Rate limited! Resets in {exc.rate_limit_info.reset}s")
    except AuthenticationError as exc:
        print(f"Auth failed: {exc.detail}")
    except NotFoundError:
        print("No census tract found for this location")
    except ValidationError as exc:
        print(f"Invalid request: {exc.detail}")
```

### Rate limit tracking

Both clients expose the `last_rate_limit` attribute after every request:

```python
result = await client.context(address="1234 Main St, Minneapolis, MN")
rl = client.last_rate_limit
print(f"{rl.remaining}/{rl.limit} requests left, resets in {rl.reset}s")
```

---

## MCP Server (AI Agent Integration)

The GeoHealth MCP server exposes all API endpoints as native tools for **Claude Desktop**, **Claude Code**, and other MCP-compatible agents. No HTTP wiring needed — agents call tools directly.

### Install and run

```bash
pip install geohealth-api[mcp]
GEOHEALTH_API_KEY=your-key python -m geohealth.mcp
```

### Claude Desktop configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "geohealth": {
      "command": "python",
      "args": ["-m", "geohealth.mcp"],
      "env": {
        "GEOHEALTH_BASE_URL": "https://geohealth-api-production.up.railway.app",
        "GEOHEALTH_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| `lookup_health_context` | Primary lookup — address/coords to tract demographics, SVI, PLACES |
| `batch_health_lookup` | Multi-address lookup (up to 50) |
| `find_nearby_tracts` | Spatial radius search |
| `compare_tracts` | Compare tracts or tract vs averages |
| `get_data_dictionary` | Field definitions with clinical context |
| `get_tract_statistics` | Data coverage by state |

### Example agent interaction

Once configured, you can ask Claude:

> "What are the social vulnerability indicators for 1234 Main St, Minneapolis, MN?"

Claude will automatically call the `lookup_health_context` tool and return a clinical summary of the tract's demographics, SVI themes, and health outcomes.
