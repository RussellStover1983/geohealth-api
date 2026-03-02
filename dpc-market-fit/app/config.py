from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Geocoding
    census_geocoder_url: str = (
        "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    )
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"

    # Census ACS
    census_api_key: str = ""
    acs_year: int = 2022

    # CDC PLACES (Socrata)
    socrata_app_token: str = ""
    cdc_places_dataset_id: str = "cwsq-ngmh"

    # CDC SVI
    cdc_svi_dataset_id: str = "4d8n-kk8a"

    # CORS
    cors_origins: str = "*"

    # Cache
    cache_maxsize: int = 4096
    cache_ttl: int = 3600

    # Scoring
    default_radius_miles: float = 5.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
