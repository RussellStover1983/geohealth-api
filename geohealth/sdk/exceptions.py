"""Exception hierarchy for the GeoHealth SDK."""

from __future__ import annotations

from geohealth.sdk.models import RateLimitInfo


class GeoHealthError(Exception):
    """Base exception for all GeoHealth API errors."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class AuthenticationError(GeoHealthError):
    """Raised on 401 or 403 responses."""


class RateLimitError(GeoHealthError):
    """Raised on 429 responses."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        rate_limit_info: RateLimitInfo | None = None,
    ) -> None:
        super().__init__(status_code, detail)
        self.rate_limit_info = rate_limit_info


class NotFoundError(GeoHealthError):
    """Raised on 404 responses."""


class ValidationError(GeoHealthError):
    """Raised on 400 or 422 responses."""
