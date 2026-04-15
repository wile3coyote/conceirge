"""Integration tests for /library endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


ADD_PAYLOAD = {
    "tmdb_id": 12345,
    "title": "Inception",
    "year": 2010,
    "overview": "A thief who steals corporate secrets.",
    "poster_url": "http://img.test/poster.jpg",
}

# Patch the background pipeline so Radarr HTTP calls don't fire during tests.
_PIPELINE_PATH = "backend.routers.library.run_library_pipeline"


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
