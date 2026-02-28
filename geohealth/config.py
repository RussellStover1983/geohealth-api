from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://geohealth:geohealth@localhost:5432/geohealth"
    )
    database_url_sync: str = (
        "postgresql://geohealth:geohealth@localhost:5432/geohealth"
    )
    census_geocoder_url: str = (
        "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    )
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    cors_origins: str = "*"
    census_api_key: str = ""
    socrata_app_token: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    narrative_max_tokens: int = 1024
    cache_maxsize: int = 4096
    cache_ttl: int = 3600
    auth_enabled: bool = False
    api_keys: str = ""
    rate_limit_per_minute: int = 60
    rate_limit_window: int = 60
    acs_current_year: int = 2022
    batch_max_size: int = 50
    webhook_max_per_key: int = 10
    webhook_timeout: int = 10
    webhook_max_retries: int = 3
    run_migrations: bool = True
    log_format: str = "text"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
