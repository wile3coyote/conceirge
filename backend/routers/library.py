import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.config import Settings, get_settings
from backend.database import get_session
from backend.models.library_item import LibraryItem, LibraryItemRead
from backend.models.release import AddToLibraryRequest
from backend.services import radarr, sabnzbd, scorer
from backend.services.library import run_grab_phase, run_library_pipeline
from backend.services.sync import reconcile_with_radarr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["library"])


class ScoredReleaseRead(BaseModel):
    """API response shape for a single scored release."""

    guid: str
    indexer_id: int
    title: str
    quality: str
    size_bytes: float  # raw bytes (size_gb * 1024**3, reconstructed for clients)
    size_gb: float
    seeders: int
    score: int
    rejected: bool
    rejection_reason: str | None
    age_hours: float | None
    indexer: str | None


class GrabRequest(BaseModel):
    guid: str
    indexer_id: int


# ---------------------------------------------------------------------------
# POST /library
# ---------------------------------------------------------------------------

@router.post("", status_code=202, response_model=LibraryItem)
async def add_to_library(
    request: AddToLibraryRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LibraryItem:
    """Add a movie to the library and kick off the background search-and-grab pipeline."""
    existing = (
        await session.exec(select(LibraryItem).where(LibraryItem.tmdb_id == request.tmdb_id))
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Movie is already in the library")

    item = LibraryItem(
        tmdb_id=request.tmdb_id,
        title=request.title,
        year=request.year,
        overview=request.overview,
        poster_url=request.poster_url,
        status="searching",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    background_tasks.add_task(run_library_pipeline, item.id, settings)
    return item


# ---------------------------------------------------------------------------
# GET /library
# ---------------------------------------------------------------------------

@router.get("", response_model=list[LibraryItemRead])
async def get_library(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[LibraryItemRead]:
    """Return all library items, newest first. Includes live download progress from SABnzbd."""
    result = await session.exec(
        select(LibraryItem).order_by(LibraryItem.created_at.desc())  # type: ignore[arg-type]
    )
    items = list(result.all())

    # Fetch SABnzbd queue once if any item is currently downloading
    progress_map: dict[str, float] = {}
    if any(i.status == "downloading" and i.download_id for i in items):
        progress_map = await sabnzbd.get_queue_progress_map(settings)

    response: list[LibraryItemRead] = []
    for item in items:
        read = LibraryItemRead.model_validate(item)
        if item.download_id:
            read.download_progress = progress_map.get(item.download_id)
        response.append(read)
    return response


# ---------------------------------------------------------------------------
# GET /library/{id}/releases
# ---------------------------------------------------------------------------

@router.get("/{item_id}/releases", response_model=list[ScoredReleaseRead])
async def get_releases(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ScoredReleaseRead]:
    """Fetch and score releases for a library item on demand.

    Returns all releases (including rejected), sorted by score descending.
    """
    item = await session.get(LibraryItem, item_id)
    if item is None or item.radarr_movie_id is None:
        raise HTTPException(status_code=404, detail="Library item not found or not yet in Radarr")

    raw_releases = await radarr.fetch_releases(item.radarr_movie_id, settings)
    scored = scorer.score_releases(raw_releases, settings)

    # Build a lookup of raw release metadata by guid so we can surface
    # seeders, age, and indexer name (fields that ScoredRelease doesn't carry).
    raw_by_guid: dict[str, dict] = {r.get("guid", ""): r for r in raw_releases}

    result: list[ScoredReleaseRead] = []
    for sr in scored:
        raw = raw_by_guid.get(sr.radarr_guid, {})
        size_bytes = sr.size_gb * 1024**3
        result.append(
            ScoredReleaseRead(
                guid=sr.radarr_guid,
                indexer_id=sr.indexer_id,
                title=sr.title,
                quality=sr.quality,
                size_bytes=size_bytes,
                size_gb=sr.size_gb,
                seeders=int(raw.get("seeders", 0) or 0),
                score=sr.score,
                rejected=sr.rejected,
                rejection_reason=sr.reject_reason,
                age_hours=raw.get("ageHours") or raw.get("age_hours"),
                indexer=raw.get("indexer"),
            )
        )
    return result


# ---------------------------------------------------------------------------
# POST /library/{id}/grab
# ---------------------------------------------------------------------------

@router.post("/{item_id}/grab", status_code=202)
async def grab_release(
    item_id: int,
    body: GrabRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Explicitly grab a specific release for a library item.

    Trusts the client's GUID and indexer_id — allows picking a rejected release.
    """
    item = await session.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")

    try:
        await radarr.grab_release(body.guid, body.indexer_id, settings)
        item.status = "grabbing"
        item.fail_reason = None
        item.updated_at = datetime.now(timezone.utc)
        await session.commit()
    except Exception as exc:
        item.status = "failed"
        item.fail_reason = str(exc)
        item.updated_at = datetime.now(timezone.utc)
        await session.commit()
        raise

    return {"status": "grabbing"}


# ---------------------------------------------------------------------------
# POST /library/{id}/auto-grab
# ---------------------------------------------------------------------------

@router.post("/{item_id}/auto-grab", status_code=202)
async def auto_grab(
    item_id: int,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Trigger an automatic fetch → score → grab-best cycle for a library item."""
    item = await session.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")

    item.status = "searching"
    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(item)

    background_tasks.add_task(run_grab_phase, item, session, settings)
    return {"status": "searching"}


# ---------------------------------------------------------------------------
# POST /library/sync
# ---------------------------------------------------------------------------

@router.post("/sync", status_code=202)
async def sync_library(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Trigger a background reconciliation of the library with Radarr."""
    background_tasks.add_task(reconcile_with_radarr, session, settings)
    return {"status": "syncing"}


# ---------------------------------------------------------------------------
# POST /library/{id}/retry
# ---------------------------------------------------------------------------

@router.post("/{item_id}/retry", response_model=LibraryItem)
async def retry_library_item(
    item_id: int,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LibraryItem:
    """Reset a failed library item to 'searching' and re-run the pipeline."""
    item = await session.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    if item.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed items can be retried")

    item.status = "searching"
    item.fail_reason = None
    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(item)

    background_tasks.add_task(run_library_pipeline, item.id, settings)
    return item


# ---------------------------------------------------------------------------
# DELETE /library/{id}  (cascading)
# ---------------------------------------------------------------------------

@router.delete("/{item_id}", status_code=204)
async def delete_library_item(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Remove a library item, cascading to Radarr and SABnzbd where applicable."""
    item = await session.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")

    # 1. Best-effort: remove from Radarr (and delete files)
    if item.radarr_movie_id is not None:
        try:
            await radarr.delete_movie(item.radarr_movie_id, settings, delete_files=True)
        except Exception:
            logger.warning(
                "delete_library_item: failed to delete radarr_movie_id=%d for item %d — continuing",
                item.radarr_movie_id,
                item_id,
                exc_info=True,
            )

    # 2. Best-effort: cancel active SABnzbd download
    if item.status == "downloading" and item.download_id:
        try:
            await sabnzbd.delete_queue_item(item.download_id, settings)
        except Exception:
            logger.warning(
                "delete_library_item: failed to cancel SABnzbd nzo_id=%s for item %d — continuing",
                item.download_id,
                item_id,
                exc_info=True,
            )

    # 3. Delete the DB row
    await session.delete(item)
    await session.commit()
