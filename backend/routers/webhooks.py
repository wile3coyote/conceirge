import logging
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.config import Settings, get_settings
from backend.database import get_session
from backend.exceptions import JellyfinError
from backend.models.library_item import LibraryItem
from backend.services import jellyfin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/radarr")
async def radarr_webhook(
    payload: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Handle Radarr On Grab and On Download webhook events."""
    event_type: str = payload.get("eventType", "")
    movie_data: dict = payload.get("movie") or {}
    tmdb_id: int | None = movie_data.get("tmdbId")

    logger.info(
        "Webhook received: eventType=%s tmdb_id=%s payload_keys=%s",
        event_type, tmdb_id, list(payload.keys()),
    )

    if not tmdb_id or event_type not in ("Grab", "Download"):
        logger.info("Webhook ignored: missing tmdb_id or unhandled eventType")
        return {"status": "ignored"}

    item = (
        await session.exec(select(LibraryItem).where(LibraryItem.tmdb_id == tmdb_id))
    ).first()

    if item is None:
        logger.warning("Webhook ignored: no LibraryItem with tmdb_id=%d", tmdb_id)
        return {"status": "ignored"}

    logger.info(
        "Webhook matched item id=%d title=%s current_status=%s",
        item.id, item.title, item.status,
    )

    if event_type == "Grab" and item.status == "grabbing":
        item.status = "downloading"
        item.download_id = payload.get("downloadId")  # SABnzbd nzo_id for progress tracking
        logger.info("Item %d: grabbing → downloading (download_id=%s)", item.id, item.download_id)
    elif event_type == "Download" and item.status in ("grabbing", "downloading"):
        try:
            await jellyfin.refresh_library(settings)
        except JellyfinError:
            pass  # don't block webhook on Jellyfin errors
        item.status = "in_library"
        logger.info("Item %d: %s → in_library", item.id, item.status)
    else:
        logger.warning(
            "Webhook ignored: eventType=%s but item status=%s (no valid transition)",
            event_type, item.status,
        )
        return {"status": "ignored"}

    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "ok"}


@router.get("/radarr/diagnose")
async def diagnose_radarr_webhook(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Check whether Radarr has a webhook notification configured pointing at this app."""
    url = f"{settings.radarr_url}/api/v3/notification"
    headers = {"X-Api-Key": settings.radarr_api_key.get_secret_value()}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
        if not response.is_success:
            return {"error": f"Radarr returned {response.status_code}", "notifications": []}
        notifications = response.json()
        webhook_entries = [
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "implementation": n.get("implementation"),
                "fields": {
                    f["name"]: f.get("value")
                    for f in n.get("fields", [])
                    if f["name"] in ("Url", "Username", "Method")
                },
                "onGrab": n.get("onGrab"),
                "onDownload": n.get("onDownload"),
            }
            for n in notifications
            if n.get("implementation") == "Webhook"
        ]
        return {
            "total_notifications": len(notifications),
            "webhook_notifications": webhook_entries,
            "hint": "Look for a Webhook pointing to http://localhost:8000/webhooks/radarr with onGrab and onDownload both true",
        }
    except httpx.RequestError as exc:
        return {"error": f"Could not reach Radarr: {exc}"}
