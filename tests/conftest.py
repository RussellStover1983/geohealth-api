import pytest
from httpx import ASGITransport, AsyncClient

from geohealth.api.main import app
from geohealth.services.rate_limiter import rate_limiter


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    """Reset the rate limiter between every test."""
    rate_limiter.clear()
    yield
    rate_limiter.clear()
