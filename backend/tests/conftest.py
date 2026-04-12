from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.config import Settings, get_settings
from backend.main import app


@pytest_asyncio.fixture
async def async_client(override_settings) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    # Inject API keys via env so pydantic-settings coerces str→SecretStr itself,
    # avoiding the Pyright limitation where str isn't accepted in __init__ for
    # SecretStr fields on BaseSettings subclasses.
    monkeypatch.setenv("RADARR_API_KEY", "test-api-key")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-jellyfin-key")
    return Settings(
        radarr_url="http://radarr.test",
        jellyfin_url="http://jellyfin.test",
        max_size_gb=40.0,
        avoid_keywords=["CAM", "HDCAM"],
    )


@pytest.fixture
def override_settings(test_settings: Settings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield test_settings
    app.dependency_overrides.clear()
