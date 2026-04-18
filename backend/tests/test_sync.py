"""Unit tests for backend.services.sync.reconcile_with_radarr.

All outbound Radarr HTTP calls are mocked via unittest.mock.patch so that
the test suite never requires a running Radarr instance.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from backend.models.library_item import LibraryItem
from backend.services.sync import reconcile_with_radarr

# ---------------------------------------------------------------------------
# Path to the radarr.list_movies function used inside sync.py
# ---------------------------------------------------------------------------
_LIST_MOVIES_PATH = "backend.services.sync.list_movies"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _radarr_movie(
    tmdb_id: int,
    radarr_id: int,
    title: str = "Test Movie",
    year: int = 2020,
    has_file: bool = False,
    overview: str | None = None,
    poster_remote_url: str | None = None,
) -> dict:
    """Return a minimal Radarr movie dict as returned by GET /api/v3/movie."""
    images = []
    if poster_remote_url:
        images.append({"coverType": "poster", "remoteUrl": poster_remote_url})
    return {
        "id": radarr_id,
        "tmdbId": tmdb_id,
        "title": title,
        "year": year,
        "hasFile": has_file,
        "overview": overview or "",
        "images": images,
    }


async def _seed_item(
    session,
    tmdb_id: int,
    title: str = "Test Movie",
    year: int = 2020,
    status: str = "idle",
    radarr_movie_id: int | None = None,
    radarr_has_file: bool = False,
    chosen_release_title: str | None = None,
    chosen_release_size_gb: float | None = None,
    chosen_release_quality: str | None = None,
    download_id: str | None = None,
) -> LibraryItem:
    item = LibraryItem(
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        status=status,
        radarr_movie_id=radarr_movie_id,
        radarr_has_file=radarr_has_file,
        chosen_release_title=chosen_release_title,
        chosen_release_size_gb=chosen_release_size_gb,
        chosen_release_quality=chosen_release_quality,
        download_id=download_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


# ===========================================================================
# Tests: Radarr-only movies → INSERT
# ===========================================================================


@pytest.mark.asyncio
async def test_radarr_only_movie_without_file_inserted_as_idle(
    override_db, test_settings
):
    """A movie in Radarr but not in Concierge is inserted with status='idle' when hasFile=False."""
    radarr_movies = [
        _radarr_movie(tmdb_id=11111, radarr_id=1, title="Inception", year=2010, has_file=False)
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 11111))
    ).first()
    assert result is not None
    assert result.title == "Inception"
    assert result.radarr_movie_id == 1
    assert result.status == "idle"
    assert result.radarr_has_file is False


@pytest.mark.asyncio
async def test_radarr_only_movie_with_file_inserted_as_in_library(
    override_db, test_settings
):
    """A movie in Radarr with hasFile=True is inserted with status='in_library'."""
    radarr_movies = [
        _radarr_movie(tmdb_id=22222, radarr_id=2, title="Dune", year=2021, has_file=True)
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 22222))
    ).first()
    assert result is not None
    assert result.status == "in_library"
    assert result.radarr_has_file is True


@pytest.mark.asyncio
async def test_radarr_only_movie_poster_url_extracted(override_db, test_settings):
    """Poster URL is extracted from Radarr images array and stored on the new item."""
    radarr_movies = [
        _radarr_movie(
            tmdb_id=33333,
            radarr_id=3,
            title="Oppenheimer",
            year=2023,
            poster_remote_url="https://image.tmdb.org/poster.jpg",
        )
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.tmdb_id == 33333))
    ).first()
    assert result is not None
    assert result.poster_url == "https://image.tmdb.org/poster.jpg"


# ===========================================================================
# Tests: Concierge-only movies → DELETE (unless in-flight)
# ===========================================================================


@pytest.mark.asyncio
async def test_concierge_only_with_radarr_id_deleted(override_db, test_settings):
    """A Concierge row (with radarr_movie_id) absent from Radarr is deleted."""
    item = await _seed_item(
        override_db, tmdb_id=44444, status="idle", radarr_movie_id=100
    )

    # Radarr returns empty list — movie is gone
    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=[]):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is None


@pytest.mark.asyncio
async def test_concierge_only_without_radarr_id_is_noop(override_db, test_settings):
    """A Concierge row with radarr_movie_id=None (failed add) is NOT deleted during sync."""
    item = await _seed_item(
        override_db, tmdb_id=55555, status="failed", radarr_movie_id=None
    )

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=[]):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is not None, "Item with radarr_movie_id=None must not be deleted by sync"


@pytest.mark.asyncio
async def test_concierge_only_grabbing_status_skipped(override_db, test_settings):
    """In-flight 'grabbing' items are skipped and NOT deleted even when absent from Radarr."""
    item = await _seed_item(
        override_db, tmdb_id=66666, status="grabbing", radarr_movie_id=200
    )

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=[]):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is not None
    assert result.status == "grabbing"


@pytest.mark.asyncio
async def test_concierge_only_downloading_status_skipped(override_db, test_settings):
    """In-flight 'downloading' items are skipped and NOT deleted even when absent from Radarr."""
    item = await _seed_item(
        override_db, tmdb_id=77777, status="downloading", radarr_movie_id=201
    )

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=[]):
        await reconcile_with_radarr(override_db, test_settings)

    result = (
        await override_db.exec(select(LibraryItem).where(LibraryItem.id == item.id))
    ).first()
    assert result is not None
    assert result.status == "downloading"


# ===========================================================================
# Tests: Both sides — metadata + radarr_has_file / status transitions
# ===========================================================================


@pytest.mark.asyncio
async def test_both_sides_has_file_false_to_true_promotes_to_in_library(
    override_db, test_settings
):
    """When Radarr's hasFile flips False→True on an 'idle' item, status→'in_library'."""
    item = await _seed_item(
        override_db,
        tmdb_id=88888,
        status="idle",
        radarr_movie_id=300,
        radarr_has_file=False,
    )

    radarr_movies = [
        _radarr_movie(tmdb_id=88888, radarr_id=300, has_file=True)
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    await override_db.refresh(item)
    assert item.status == "in_library"
    assert item.radarr_has_file is True


@pytest.mark.asyncio
async def test_both_sides_has_file_true_to_false_reverts_to_idle(
    override_db, test_settings
):
    """When Radarr's hasFile flips True→False on an 'in_library' item, status→'idle' and release fields cleared."""
    item = await _seed_item(
        override_db,
        tmdb_id=99999,
        status="in_library",
        radarr_movie_id=400,
        radarr_has_file=True,
        chosen_release_title="Movie.2160p.WEB-DL",
        chosen_release_size_gb=28.0,
        chosen_release_quality="2160p",
        download_id="nzo_stale",
    )

    radarr_movies = [
        _radarr_movie(tmdb_id=99999, radarr_id=400, has_file=False)
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    await override_db.refresh(item)
    assert item.status == "idle"
    assert item.radarr_has_file is False
    assert item.chosen_release_title is None
    assert item.chosen_release_size_gb is None
    assert item.chosen_release_quality is None
    assert item.download_id is None


@pytest.mark.asyncio
async def test_both_sides_metadata_updated(override_db, test_settings):
    """Title / year / overview changes from Radarr are written back to the DB."""
    item = await _seed_item(
        override_db,
        tmdb_id=10001,
        title="Old Title",
        year=2000,
        radarr_movie_id=500,
    )

    radarr_movies = [
        _radarr_movie(
            tmdb_id=10001,
            radarr_id=500,
            title="New Title",
            year=2001,
        )
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    await override_db.refresh(item)
    assert item.title == "New Title"
    assert item.year == 2001


@pytest.mark.asyncio
async def test_both_sides_no_changes_no_unnecessary_update(override_db, test_settings):
    """When nothing changes, the row is not mutated (updated_at stays the same)."""
    from datetime import datetime, timezone

    item = await _seed_item(
        override_db,
        tmdb_id=10002,
        title="Stable Movie",
        year=2015,
        radarr_movie_id=600,
        radarr_has_file=False,
    )
    original_updated_at = item.updated_at

    radarr_movies = [
        _radarr_movie(
            tmdb_id=10002,
            radarr_id=600,
            title="Stable Movie",
            year=2015,
            has_file=False,
        )
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    await override_db.refresh(item)
    # When there are no field changes, the sync should NOT bump updated_at.
    # (The sync only calls session.add(item) and sets item.updated_at when changed=True.)
    assert item.updated_at == original_updated_at


@pytest.mark.asyncio
async def test_empty_radarr_and_db_is_noop(override_db, test_settings):
    """Both sides empty → no rows inserted, no errors."""
    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=[]):
        await reconcile_with_radarr(override_db, test_settings)

    result = await override_db.exec(select(LibraryItem))
    assert list(result.all()) == []


@pytest.mark.asyncio
async def test_multiple_radarr_movies_all_inserted(override_db, test_settings):
    """Multiple Radarr-only movies are all inserted in a single reconcile call."""
    radarr_movies = [
        _radarr_movie(tmdb_id=20001, radarr_id=1001, title="Movie A", has_file=False),
        _radarr_movie(tmdb_id=20002, radarr_id=1002, title="Movie B", has_file=True),
        _radarr_movie(tmdb_id=20003, radarr_id=1003, title="Movie C", has_file=False),
    ]

    with patch(_LIST_MOVIES_PATH, new_callable=AsyncMock, return_value=radarr_movies):
        await reconcile_with_radarr(override_db, test_settings)

    result = await override_db.exec(select(LibraryItem))
    items = list(result.all())
    assert len(items) == 3
    tmdb_ids = {item.tmdb_id for item in items}
    assert tmdb_ids == {20001, 20002, 20003}
