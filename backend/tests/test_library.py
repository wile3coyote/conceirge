"""Integration tests for /library endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import select

from backend.exceptions import RadarrError
from backend.models.app_settings import AppSettings
from backend.models.library_item import LibraryItem


ADD_PAYLOAD = {
    "tmdb_id": 12345,
    "title": "Inception",
    "year": 2010,
    "overview": "A thief who steals corporate secrets.",
    "poster_url": "http://img.test/poster.jpg",
}

# Patch the background pipeline so Radarr HTTP calls don't fire during tests.
_PIPELINE_PATH = "backend.routers.library.run_library_pipeline"
_RUN_GRAB_PHASE_PATH = "backend.routers.library.run_grab_phase"

# ---------------------------------------------------------------------------
# Sample release dicts (raw Radarr format) used by GET /releases tests
# ---------------------------------------------------------------------------
_RELEASE_2160P = {
    "guid": "guid-2160p",
    "indexerId": 1,
    "title": "Inception.2010.2160p.WEB-DL.x265",
    "size": int(28 * 1024**3),  # 28 GB — well within 40 GB limit
    "quality": {"quality": {"resolution": 2160}},
    "seeders": 50,
    "ageHours": 24.0,
    "indexer": "TestIndexer",
}
_RELEASE_TOO_LARGE = {
    "guid": "guid-toolarge",
    "indexerId": 1,
    "title": "Inception.2010.2160p.BluRay.x265",
    "size": int(50 * 1024**3),  # 50 GB — exceeds 40 GB hard limit
    "quality": {"quality": {"resolution": 2160}},
    "seeders": 10,
    "ageHours": 48.0,
    "indexer": "TestIndexer",
}
_RELEASE_BLOCKLIST = {
    "guid": "guid-cam",
    "indexerId": 1,
    "title": "Inception.2010.CAM.720p",
    "size": int(2 * 1024**3),  # 2 GB — small but blocked
    "quality": {"quality": {"resolution": 720}},
    "seeders": 5,
    "ageHours": 2.0,
    "indexer": "TestIndexer",
}


@pytest.mark.asyncio
async def test_add_to_library_returns_202(async_client):
    """POST /library creates an item with status 'searching' and returns 202."""
    with patch(_PIPELINE_PATH, new_callable=AsyncMock):
        response = await async_client.post("/library", json=ADD_PAYLOAD)

    assert response.status_code == 202
    body = response.json()
    assert body["tmdb_id"] == 12345
    assert body["title"] == "Inception"
    assert body["status"] == "searching"
    assert isinstance(body["id"], int)


@pytest.mark.asyncio
async def test_add_to_library_fires_pipeline(async_client):
    """Background pipeline is scheduled once when the item is created."""
    with patch(_PIPELINE_PATH, new_callable=AsyncMock) as mock_pipeline:
        await async_client.post("/library", json=ADD_PAYLOAD)

    mock_pipeline.assert_called_once()


@pytest.mark.asyncio
async def test_add_duplicate_tmdb_id_returns_409(async_client):
    """Adding the same tmdb_id twice → 409 Conflict."""
    with patch(_PIPELINE_PATH, new_callable=AsyncMock):
        await async_client.post("/library", json=ADD_PAYLOAD)
        response = await async_client.post("/library", json=ADD_PAYLOAD)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_library_returns_all_items(async_client):
    """GET /library returns all persisted items."""
    with patch(_PIPELINE_PATH, new_callable=AsyncMock):
        await async_client.post("/library", json=ADD_PAYLOAD)

    response = await async_client.get("/library")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_library_empty(async_client):
    """GET /library returns [] when no items exist."""
    response = await async_client.get("/library")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_delete_library_item(async_client):
    """DELETE /library/{id} removes the item; subsequent GET returns []."""
    with patch(_PIPELINE_PATH, new_callable=AsyncMock):
        add_resp = await async_client.post("/library", json=ADD_PAYLOAD)
    item_id = add_resp.json()["id"]

    del_resp = await async_client.delete(f"/library/{item_id}")
    assert del_resp.status_code == 204

    get_resp = await async_client.get("/library")
    assert get_resp.json() == []


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(async_client):
    """DELETE on an unknown id → 404."""
    response = await async_client.delete("/library/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retry_non_failed_item_returns_400(async_client):
    """Retry a 'searching' item (not failed) → 400."""
    with patch(_PIPELINE_PATH, new_callable=AsyncMock):
        add_resp = await async_client.post("/library", json=ADD_PAYLOAD)
        item_id = add_resp.json()["id"]

        retry_resp = await async_client.post(f"/library/{item_id}/retry")

    assert retry_resp.status_code == 400


@pytest.mark.asyncio
async def test_retry_nonexistent_returns_404(async_client):
    """Retry on an unknown id → 404."""
    response = await async_client.post("/library/9999/retry")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retry_failed_item_resets_to_searching(async_client, override_db):
    """Retry on a failed item resets status to 'searching' and fires pipeline."""
    from backend.models.library_item import LibraryItem

    # Directly insert a failed item into the test DB
    item = LibraryItem(
        tmdb_id=99999,
        title="Dune",
        year=2021,
        status="failed",
        fail_reason="No releases",
    )
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)

    with patch(_PIPELINE_PATH, new_callable=AsyncMock) as mock_pipeline:
        response = await async_client.post(f"/library/{item.id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "searching"
    assert response.json()["fail_reason"] is None
    mock_pipeline.assert_called_once()


# ===========================================================================
# New tests: auto_grab=False path
# ===========================================================================


async def _seed_item(
    session,
    tmdb_id: int = 12345,
    title: str = "Inception",
    year: int = 2010,
    status: str = "searching",
    radarr_movie_id: int | None = None,
    download_id: str | None = None,
) -> LibraryItem:
    item = LibraryItem(
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        status=status,
        radarr_movie_id=radarr_movie_id,
        download_id=download_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@pytest.mark.asyncio
async def test_auto_grab_false_item_ends_at_idle(override_db, test_settings):
    """When AppSettings.auto_grab=False, run_library_pipeline sets status to 'idle'.

    This tests the service layer directly (not via HTTP) so the test session is
    injected without going through the real ``async_session`` factory.
    """
    from backend.services.library import run_library_pipeline

    # Insert an AppSettings row with auto_grab disabled
    app_settings = AppSettings(auto_grab=False)
    override_db.add(app_settings)
    await override_db.commit()

    # Insert the LibraryItem in "searching" state (as the router would create it)
    item = LibraryItem(
        tmdb_id=ADD_PAYLOAD["tmdb_id"],
        title=ADD_PAYLOAD["title"],
        year=ADD_PAYLOAD["year"],
        status="searching",
    )
    override_db.add(item)
    await override_db.commit()
    await override_db.refresh(item)
    item_id = item.id

    # Patch radarr.lookup_movie to return a movie already in Radarr (id > 0) so
    # Phase 1 completes without calling add_movie, then the auto_grab=False branch
    # should short-circuit and set status to "idle".
    # Patch async_session to yield our test session so the pipeline reads from
    # the same in-memory DB that has the AppSettings row.
    with (
        patch(
            "backend.services.library.radarr.lookup_movie",
            new_callable=AsyncMock,
            return_value=[{"id": 999, "tmdbId": ADD_PAYLOAD["tmdb_id"], "title": ADD_PAYLOAD["title"], "year": ADD_PAYLOAD["year"]}],
        ),
        patch(
            "backend.services.library.async_session",
        ) as mock_async_session,
    ):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=override_db)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_async_session.return_value = cm

        await run_library_pipeline(item_id, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item_id))
    ).first()
    assert result is not None
    assert result.status == "idle", f"Expected 'idle', got {result.status!r}"


# ===========================================================================
# New tests: GET /library/{id}/releases
# ===========================================================================


@pytest.mark.asyncio
async def test_get_releases_returns_all_scored(async_client, override_db):
    """GET /library/{id}/releases returns all releases (good + rejected) sorted score-desc."""
    item = await _seed_item(override_db, radarr_movie_id=777)

    raw_releases = [_RELEASE_2160P, _RELEASE_TOO_LARGE, _RELEASE_BLOCKLIST]

    with patch(
        "backend.routers.library.radarr.fetch_releases",
        new_callable=AsyncMock,
        return_value=raw_releases,
    ):
        response = await async_client.get(f"/library/{item.id}/releases")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    # First entry must be the highest-scoring non-rejected release
    assert data[0]["guid"] == "guid-2160p"
    assert data[0]["rejected"] is False
    assert data[0]["rejection_reason"] is None

    # The other two must be rejected with a reason populated
    rejected = [r for r in data if r["rejected"]]
    assert len(rejected) == 2
    for r in rejected:
        assert r["rejection_reason"] is not None and r["rejection_reason"] != ""

    # All entries must have the required shape fields
    for entry in data:
        for field in ("guid", "score", "quality", "size_gb", "rejected", "rejection_reason"):
            assert field in entry, f"Missing field {field!r} in {entry}"


@pytest.mark.asyncio
async def test_get_releases_sorted_by_score_desc(async_client, override_db):
    """Non-rejected releases appear before rejected ones."""
    item = await _seed_item(override_db, radarr_movie_id=777)

    with patch(
        "backend.routers.library.radarr.fetch_releases",
        new_callable=AsyncMock,
        return_value=[_RELEASE_BLOCKLIST, _RELEASE_2160P, _RELEASE_TOO_LARGE],
    ):
        response = await async_client.get(f"/library/{item.id}/releases")

    assert response.status_code == 200
    data = response.json()
    scores = [r["score"] for r in data if not r["rejected"]]
    # All non-rejected items must come first and be in descending order
    assert scores == sorted(scores, reverse=True)
    # All rejected items come after all non-rejected
    first_rejected = next((i for i, r in enumerate(data) if r["rejected"]), len(data))
    for i, r in enumerate(data):
        if not r["rejected"]:
            assert i < first_rejected


@pytest.mark.asyncio
async def test_get_releases_item_not_found_returns_404(async_client, override_db):
    """GET /library/9999/releases → 404 when item does not exist."""
    response = await async_client.get("/library/9999/releases")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_releases_no_radarr_id_returns_404(async_client, override_db):
    """GET /library/{id}/releases → 404 when item has no radarr_movie_id yet."""
    item = await _seed_item(override_db, radarr_movie_id=None)
    response = await async_client.get(f"/library/{item.id}/releases")
    assert response.status_code == 404


# ===========================================================================
# New tests: POST /library/{id}/grab
# ===========================================================================


@pytest.mark.asyncio
async def test_grab_release_success(async_client, override_db):
    """POST /library/{id}/grab → status transitions to 'grabbing', returns 202."""
    item = await _seed_item(override_db, status="idle", radarr_movie_id=777)

    with patch(
        "backend.routers.library.radarr.grab_release",
        new_callable=AsyncMock,
    ):
        response = await async_client.post(
            f"/library/{item.id}/grab",
            json={"guid": "guid-2160p", "indexer_id": 1},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "grabbing"

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result.status == "grabbing"
    assert result.fail_reason is None


@pytest.mark.asyncio
async def test_grab_release_radarr_error_returns_502(async_client, override_db):
    """POST /library/{id}/grab → 502 when Radarr raises RadarrError; item status → 'failed'."""
    item = await _seed_item(override_db, status="idle", radarr_movie_id=777)

    with patch(
        "backend.routers.library.radarr.grab_release",
        new_callable=AsyncMock,
        side_effect=RadarrError("Radarr connection refused", code="radarr_error"),
    ):
        response = await async_client.post(
            f"/library/{item.id}/grab",
            json={"guid": "guid-bad", "indexer_id": 1},
        )

    assert response.status_code == 502

    # Refresh from DB — status must be "failed"
    await override_db.refresh(item)
    assert item.status == "failed"
    assert item.fail_reason is not None


@pytest.mark.asyncio
async def test_grab_release_item_not_found_returns_404(async_client, override_db):
    """POST /library/9999/grab → 404 when item does not exist."""
    response = await async_client.post(
        "/library/9999/grab",
        json={"guid": "guid-x", "indexer_id": 1},
    )
    assert response.status_code == 404


# ===========================================================================
# New tests: POST /library/{id}/auto-grab
# ===========================================================================


@pytest.mark.asyncio
async def test_auto_grab_returns_202_and_sets_searching(async_client, override_db):
    """POST /library/{id}/auto-grab → 202, status transitions to 'searching' synchronously."""
    item = await _seed_item(override_db, status="idle", radarr_movie_id=777)

    with patch(_RUN_GRAB_PHASE_PATH, new_callable=AsyncMock):
        response = await async_client.post(f"/library/{item.id}/auto-grab")

    assert response.status_code == 202
    assert response.json()["status"] == "searching"

    # Verify DB was updated synchronously (before background task)
    await override_db.refresh(item)
    assert item.status == "searching"


@pytest.mark.asyncio
async def test_auto_grab_item_not_found_returns_404(async_client, override_db):
    """POST /library/9999/auto-grab → 404."""
    response = await async_client.post("/library/9999/auto-grab")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_auto_grab_schedules_run_grab_phase(async_client, override_db):
    """Ensure run_grab_phase is scheduled as a background task."""
    item = await _seed_item(override_db, status="idle", radarr_movie_id=777)

    # We patch BackgroundTasks.add_task to intercept what gets scheduled.
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        response = await async_client.post(f"/library/{item.id}/auto-grab")

    assert response.status_code == 202
    # Verify add_task was called with run_grab_phase as the callable
    from backend.services.library import run_grab_phase
    calls = [call for call in mock_add_task.call_args_list]
    assert any(call.args[0] is run_grab_phase for call in calls), (
        f"run_grab_phase not found in BackgroundTasks.add_task calls: {calls}"
    )


# ===========================================================================
# New tests: DELETE /library/{id} cascading
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_cascades_radarr_and_sabnzbd(async_client, override_db):
    """DELETE /library/{id} calls radarr.delete_movie and sabnzbd.delete_queue_item."""
    item = await _seed_item(
        override_db,
        status="downloading",
        radarr_movie_id=42,
        download_id="nzo_abc123",
    )

    with (
        patch(
            "backend.routers.library.radarr.delete_movie",
            new_callable=AsyncMock,
        ) as mock_radarr_del,
        patch(
            "backend.routers.library.sabnzbd.delete_queue_item",
            new_callable=AsyncMock,
        ) as mock_sabnzbd_del,
    ):
        response = await async_client.delete(f"/library/{item.id}")

    assert response.status_code == 204
    mock_radarr_del.assert_called_once()
    mock_sabnzbd_del.assert_called_once()

    # Row must be gone
    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is None


@pytest.mark.asyncio
async def test_delete_radarr_error_still_deletes_row(async_client, override_db):
    """DELETE /library/{id} deletes the DB row even when radarr.delete_movie raises."""
    item = await _seed_item(
        override_db,
        status="in_library",
        radarr_movie_id=42,
    )

    with patch(
        "backend.routers.library.radarr.delete_movie",
        new_callable=AsyncMock,
        side_effect=RadarrError("Radarr not available"),
    ):
        response = await async_client.delete(f"/library/{item.id}")

    assert response.status_code == 204

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is None


@pytest.mark.asyncio
async def test_delete_no_radarr_id_skips_radarr_call(async_client, override_db):
    """DELETE /library/{id} skips radarr.delete_movie when radarr_movie_id is None."""
    item = await _seed_item(override_db, status="failed", radarr_movie_id=None)

    with patch(
        "backend.routers.library.radarr.delete_movie",
        new_callable=AsyncMock,
    ) as mock_radarr_del:
        response = await async_client.delete(f"/library/{item.id}")

    assert response.status_code == 204
    mock_radarr_del.assert_not_called()

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is None


@pytest.mark.asyncio
async def test_delete_not_downloading_skips_sabnzbd(async_client, override_db):
    """SABnzbd cancel is only called when status='downloading'; idle items skip it."""
    item = await _seed_item(
        override_db,
        status="in_library",
        radarr_movie_id=42,
        download_id="nzo_shouldnotcancel",
    )

    with (
        patch("backend.routers.library.radarr.delete_movie", new_callable=AsyncMock),
        patch(
            "backend.routers.library.sabnzbd.delete_queue_item",
            new_callable=AsyncMock,
        ) as mock_sabnzbd_del,
    ):
        response = await async_client.delete(f"/library/{item.id}")

    assert response.status_code == 204
    mock_sabnzbd_del.assert_not_called()
