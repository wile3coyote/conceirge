from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.config import Settings, get_settings
from backend.database import get_session
from backend.models.library_item import LibraryItem
from backend.models.release import AddToLibraryRequest
from backend.services.library import run_library_pipeline

router = APIRouter(prefix="/library", tags=["library"])


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


@router.get("", response_model=list[LibraryItem])
async def get_library(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[LibraryItem]:
    """Return all library items, newest first."""
    result = await session.exec(
        select(LibraryItem).order_by(LibraryItem.created_at.desc())  # type: ignore[arg-type]
    )
    return list(result.all())


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


@router.delete("/{item_id}", status_code=204)
async def delete_library_item(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Remove a library item."""
    item = await session.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    await session.delete(item)
    await session.commit()
