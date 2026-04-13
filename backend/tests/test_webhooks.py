"""Integration tests for POST /webhooks/radarr."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from backend.models.library_item import LibraryItem


async def _seed_item(
    session, tmdb_id: int = 12345, status: str = "grabbing"
) -> LibraryItem:
    item = LibraryItem(tmdb_id=tmdb_id, title="Inception", year=2010, status=status)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@pytest.mark.asyncio
async def test_on_grab_sets_status_downloading(async_client, override_db):
    """Radarr 'Grab' event → library item status becomes 'downloading'."""
    await _seed_item(override_db, tmdb_id=12345, status="grabbing")

    response = await async_client.post(
        "/webhooks/radarr",
        json={"eventType": "Grab", "movie": {"tmdbId": 12345}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 12345))
    ).first()
    assert result is not None
    assert result.status == "downloading"


@pytest.mark.asyncio
async def test_on_download_refreshes_jellyfin_and_sets_in_library(
    async_client, override_db
):
    """Radarr 'Download' event → Jellyfin refresh called, status becomes 'in_library'."""
    await _seed_item(override_db, tmdb_id=12345, status="downloading")

    with patch(
        "backend.routers.webhooks.jellyfin.refresh_library",
        new_callable=AsyncMock,
    ) as mock_refresh:
        response = await async_client.post(
            "/webhooks/radarr",
            json={"eventType": "Download", "movie": {"tmdbId": 12345}},
        )

    assert response.status_code == 200
    mock_refresh.assert_called_once()

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 12345))
    ).first()
    assert result is not None
    assert result.status == "in_library"


@pytest.mark.asyncio
async def test_on_download_jellyfin_error_still_sets_in_library(
    async_client, override_db
):
    """Jellyfin error on 'Download' event is swallowed — item still reaches 'in_library'."""
    await _seed_item(override_db, tmdb_id=12345, status="downloading")

    from backend.exceptions import JellyfinError

    with patch(
        "backend.routers.webhooks.jellyfin.refresh_library",
        side_effect=JellyfinError("Jellyfin unreachable"),
    ):
        response = await async_client.post(
            "/webhooks/radarr",
            json={"eventType": "Download", "movie": {"tmdbId": 12345}},
        )

    assert response.status_code == 200

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 12345))
    ).first()
    assert result is not None
    assert result.status == "in_library"


@pytest.mark.asyncio
async def test_unknown_event_type_is_ignored(async_client, override_db):
    """Event types other than 'Grab' and 'Download' return ignored."""
    await _seed_item(override_db, tmdb_id=12345)

    response = await async_client.post(
        "/webhooks/radarr",
        json={"eventType": "Test", "movie": {"tmdbId": 12345}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_missing_tmdb_id_is_ignored(async_client, override_db):
    """Webhook without tmdbId returns ignored."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={"eventType": "Grab", "movie": {}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_no_matching_library_item_is_ignored(async_client, override_db):
    """Grab event for a tmdbId not in library returns ignored."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={"eventType": "Grab", "movie": {"tmdbId": 99999}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_on_grab_ignores_non_grabbing_status(async_client, override_db):
    """Grab webhook does not regress an item already past 'grabbing'."""
    await _seed_item(override_db, tmdb_id=12345, status="downloading")

    response = await async_client.post(
        "/webhooks/radarr",
        json={"eventType": "Grab", "movie": {"tmdbId": 12345}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 12345))
    ).first()
    assert result is not None
    assert result.status == "downloading"


@pytest.mark.asyncio
async def test_on_download_ignores_non_downloading_status(async_client, override_db):
    """Download webhook does not overwrite a 'failed' item."""
    await _seed_item(override_db, tmdb_id=12345, status="failed")

    with patch(
        "backend.routers.webhooks.jellyfin.refresh_library",
        new_callable=AsyncMock,
    ) as mock_refresh:
        response = await async_client.post(
            "/webhooks/radarr",
            json={"eventType": "Download", "movie": {"tmdbId": 12345}},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    mock_refresh.assert_not_called()

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 12345))
    ).first()
    assert result is not None
    assert result.status == "failed"
