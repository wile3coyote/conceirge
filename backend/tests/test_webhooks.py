"""Integration tests for POST /webhooks/radarr."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from backend.models.library_item import LibraryItem
from backend.models.app_settings import AppSettings


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


# ===========================================================================
# New tests: MovieAdded event
# ===========================================================================


@pytest.mark.asyncio
async def test_movie_added_new_item_without_file_inserts_idle(async_client, override_db):
    """MovieAdded with hasFile=false → new LibraryItem with status='idle'."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieAdded",
            "movie": {
                "tmdbId": 55555,
                "id": 100,
                "title": "Dune",
                "year": 2021,
                "overview": "Sand worms.",
                "hasFile": False,
                "images": [],
            },
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 55555))
    ).first()
    assert result is not None
    assert result.status == "idle"
    assert result.radarr_movie_id == 100
    assert result.title == "Dune"


@pytest.mark.asyncio
async def test_movie_added_new_item_with_file_inserts_in_library(async_client, override_db):
    """MovieAdded with hasFile=true → new LibraryItem with status='in_library'."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieAdded",
            "movie": {
                "tmdbId": 55556,
                "id": 101,
                "title": "Oppenheimer",
                "year": 2023,
                "hasFile": True,
                "images": [],
            },
        },
    )
    assert response.status_code == 200

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 55556))
    ).first()
    assert result is not None
    assert result.status == "in_library"
    assert result.radarr_has_file is True


@pytest.mark.asyncio
async def test_movie_added_existing_unlinked_sets_radarr_id(async_client, override_db):
    """MovieAdded for an existing row with radarr_movie_id=None links it."""
    # Pre-insert without radarr_movie_id
    item = LibraryItem(tmdb_id=77777, title="Tenet", year=2020, radarr_movie_id=None)
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)

    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieAdded",
            "movie": {
                "tmdbId": 77777,
                "id": 200,
                "title": "Tenet",
                "year": 2020,
                "hasFile": False,
                "images": [],
            },
        },
    )
    assert response.status_code == 200

    await override_db.refresh(item)
    assert item.radarr_movie_id == 200


@pytest.mark.asyncio
async def test_movie_added_missing_tmdb_id_ignored(async_client, override_db):
    """MovieAdded with no tmdbId → no DB insert, returns ok=True."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieAdded",
            "movie": {},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True


@pytest.mark.asyncio
async def test_movie_added_poster_url_extracted(async_client, override_db):
    """MovieAdded extracts poster URL from images array correctly."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieAdded",
            "movie": {
                "tmdbId": 66666,
                "id": 102,
                "title": "Interstellar",
                "year": 2014,
                "hasFile": False,
                "images": [
                    {"coverType": "fanart", "remoteUrl": "http://fanart.test/img.jpg"},
                    {"coverType": "poster", "remoteUrl": "http://poster.test/p.jpg"},
                ],
            },
        },
    )
    assert response.status_code == 200

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 66666))
    ).first()
    assert result is not None
    assert result.poster_url == "http://poster.test/p.jpg"


# ===========================================================================
# New tests: MovieDelete event
# ===========================================================================


@pytest.mark.asyncio
async def test_movie_delete_normal_removes_row(async_client, override_db):
    """MovieDelete removes the LibraryItem from the DB."""
    item = LibraryItem(
        tmdb_id=88888, title="The Dark Knight", year=2008, status="in_library", radarr_movie_id=300
    )
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)

    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieDelete",
            "movie": {"tmdbId": 88888, "id": 300},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 88888))
    ).first()
    assert result is None


@pytest.mark.asyncio
async def test_movie_delete_guarded_grabbing_status_not_deleted(async_client, override_db):
    """MovieDelete is skipped when item is in 'grabbing' status (in-flight)."""
    item = LibraryItem(
        tmdb_id=99991, title="Parasite", year=2019, status="grabbing", radarr_movie_id=301
    )
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)

    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieDelete",
            "movie": {"tmdbId": 99991, "id": 301},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True

    # Row must still exist
    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 99991))
    ).first()
    assert result is not None
    assert result.status == "grabbing"


@pytest.mark.asyncio
async def test_movie_delete_guarded_downloading_status_not_deleted(async_client, override_db):
    """MovieDelete is skipped when item is in 'downloading' status (in-flight)."""
    item = LibraryItem(
        tmdb_id=99992, title="Joker", year=2019, status="downloading", radarr_movie_id=302
    )
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)

    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieDelete",
            "movie": {"tmdbId": 99992, "id": 302},
        },
    )
    assert response.status_code == 200

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 99992))
    ).first()
    assert result is not None
    assert result.status == "downloading"


@pytest.mark.asyncio
async def test_movie_delete_no_matching_item_is_noop(async_client, override_db):
    """MovieDelete for unknown tmdbId returns ok=True without crash."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieDelete",
            "movie": {"tmdbId": 11111, "id": 999},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True


# ===========================================================================
# New tests: MovieFileDelete event
# ===========================================================================


@pytest.mark.asyncio
async def test_movie_file_delete_resets_to_idle(async_client, override_db):
    """MovieFileDelete transitions 'in_library' item to 'idle' and clears release fields."""
    item = LibraryItem(
        tmdb_id=33333,
        title="Avatar",
        year=2009,
        status="in_library",
        radarr_movie_id=400,
        radarr_has_file=True,
        chosen_release_title="Avatar.2009.2160p.WEB-DL",
        chosen_release_size_gb=28.0,
        chosen_release_quality="2160p",
        download_id="nzo_xyz",
    )
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)

    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieFileDelete",
            "movie": {"tmdbId": 33333},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True

    await override_db.refresh(item)
    assert item.status == "idle"
    assert item.radarr_has_file is False
    assert item.chosen_release_title is None
    assert item.chosen_release_size_gb is None
    assert item.chosen_release_quality is None
    assert item.download_id is None


@pytest.mark.asyncio
async def test_movie_file_delete_missing_tmdb_id_ignored(async_client, override_db):
    """MovieFileDelete with no tmdbId returns ok=True without crash."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieFileDelete",
            "movie": {},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True


@pytest.mark.asyncio
async def test_movie_file_delete_no_matching_item_is_noop(async_client, override_db):
    """MovieFileDelete for unknown tmdbId returns ok=True without crash."""
    response = await async_client.post(
        "/webhooks/radarr",
        json={
            "eventType": "MovieFileDelete",
            "movie": {"tmdbId": 44444},
        },
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True


@pytest.mark.asyncio
async def test_on_download_with_fcm_token_calls_fcm(async_client, override_db):
    """Download event with FCM token configured → fcm.send_download_complete is called."""
    # Seed an AppSettings row with an FCM token
    app_settings = AppSettings(fcm_token="test-fcm-token")
    override_db.add(app_settings)
    await override_db.commit()

    await _seed_item(override_db, tmdb_id=12345, status="downloading")

    with (
        patch("backend.routers.webhooks.jellyfin.refresh_library", new_callable=AsyncMock),
        patch("backend.routers.webhooks.fcm.send_download_complete", new_callable=AsyncMock) as mock_fcm,
    ):
        # We need firebase_project_id to be non-empty for FCM to fire
        from backend.config import Settings
        settings_with_firebase = Settings(
            radarr_url="http://radarr.test",
            radarr_api_key="test-api-key",
            jellyfin_url="http://jellyfin.test",
            jellyfin_api_key="test-jellyfin-key",
            firebase_project_id="my-firebase-project",
        )
        from backend.main import app
        from backend.config import get_settings
        original_override = app.dependency_overrides.get(get_settings)
        app.dependency_overrides[get_settings] = lambda: settings_with_firebase
        try:
            response = await async_client.post(
                "/webhooks/radarr",
                json={"eventType": "Download", "movie": {"tmdbId": 12345}},
            )
        finally:
            if original_override is not None:
                app.dependency_overrides[get_settings] = original_override
            else:
                app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    mock_fcm.assert_called_once()
