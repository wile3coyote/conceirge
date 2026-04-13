"""Unit tests for backend/services/jellyfin.py."""

import httpx
import pytest
import respx
from httpx import Response

from backend.exceptions import JellyfinError
from backend.services.jellyfin import refresh_library


@pytest.fixture
def jellyfin_settings(test_settings):
    """Settings with Jellyfin URL + API key set."""
    return test_settings


@pytest.mark.asyncio
async def test_refresh_library_success(jellyfin_settings):
    """204 from Jellyfin → no exception raised."""
    with respx.mock() as mock:
        mock.post("http://jellyfin.test/Library/Refresh").mock(
            return_value=Response(204)
        )
        await refresh_library(jellyfin_settings)


@pytest.mark.asyncio
async def test_refresh_library_200_also_succeeds(jellyfin_settings):
    """200 response (some Jellyfin versions) → no exception."""
    with respx.mock() as mock:
        mock.post("http://jellyfin.test/Library/Refresh").mock(
            return_value=Response(200)
        )
        await refresh_library(jellyfin_settings)


@pytest.mark.asyncio
async def test_refresh_library_unreachable_raises_jellyfin_error(jellyfin_settings):
    """Connection error → JellyfinError with 'unreachable' in message."""
    with respx.mock() as mock:
        mock.post("http://jellyfin.test/Library/Refresh").mock(
            side_effect=httpx.ConnectError("refused")
        )
        with pytest.raises(JellyfinError, match="unreachable"):
            await refresh_library(jellyfin_settings)


@pytest.mark.asyncio
async def test_refresh_library_non_2xx_raises_jellyfin_error(jellyfin_settings):
    """Non-success HTTP status → JellyfinError with 'failed' in message."""
    with respx.mock() as mock:
        mock.post("http://jellyfin.test/Library/Refresh").mock(
            return_value=Response(500)
        )
        with pytest.raises(JellyfinError, match="failed"):
            await refresh_library(jellyfin_settings)


@pytest.mark.asyncio
async def test_refresh_library_missing_api_key_raises(monkeypatch):
    """Empty Jellyfin API key → JellyfinError config_error."""
    from backend.config import Settings

    monkeypatch.setenv("RADARR_API_KEY", "x")
    monkeypatch.setenv("JELLYFIN_API_KEY", "")
    settings = Settings(jellyfin_url="http://jellyfin.test")

    with pytest.raises(JellyfinError, match="not configured"):
        await refresh_library(settings)
