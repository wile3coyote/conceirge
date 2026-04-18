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
from backend.models.app_settings import AppSettings
from backend.models.library_item import LibraryItem
from backend.services import fcm, jellyfin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/radarr")
async def radarr_webhook(
    payload: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Handle Radarr webhook events: Grab, Download, MovieAdded, MovieDelete, MovieFileDelete."""
    event_type: str = payload.get("eventType", "")
    movie_data: dict = payload.get("movie") or {}
    tmdb_id: int | None = movie_data.get("tmdbId")

    logger.info(
        "Webhook received: eventType=%s tmdb_id=%s payload_keys=%s",
        event_type, tmdb_id, list(payload.keys()),
    )

    # ------------------------------------------------------------------ #
    # Grab / Download — existing handlers (unchanged)                     #
    # ------------------------------------------------------------------ #

    if event_type in ("Grab", "Download"):
        if not tmdb_id:
            logger.info("Webhook ignored: missing tmdb_id for eventType=%s", event_type)
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

            app_settings_row = (await session.exec(select(AppSettings))).first()
            if app_settings_row and app_settings_row.fcm_token and settings.firebase_project_id:
                try:
                    await fcm.send_download_complete(
                        project_id=settings.firebase_project_id,
                        service_account_path=settings.firebase_service_account_path,
                        fcm_token=app_settings_row.fcm_token,
                        title=item.title,
                        year=item.year,
                        tmdb_id=item.tmdb_id,
                        quality=item.chosen_release_quality,
                        library_item_id=item.id,
                    )
                    logger.info("FCM notification sent for item %d", item.id)
                except Exception as exc:
                    logger.error("FCM notification failed for item %d: %s", item.id, exc)
        else:
            logger.warning(
                "Webhook ignored: eventType=%s but item status=%s (no valid transition)",
                event_type, item.status,
            )
            return {"status": "ignored"}

        item.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return {"status": "ok"}

    # ------------------------------------------------------------------ #
    # MovieAdded — upsert LibraryItem from Radarr                        #
    # ------------------------------------------------------------------ #

    elif event_type == "MovieAdded":
        # Guard: Radarr test webhooks have no movie payload; ignore silently.
        if not tmdb_id:
            logger.info("MovieAdded ignored: no tmdb_id in payload")
            return {"ok": True}

        radarr_movie_id: int | None = movie_data.get("id")
        title: str = movie_data.get("title", "")
        year: int = movie_data.get("year", 0)
        overview: str | None = movie_data.get("overview")
        has_file: bool = movie_data.get("hasFile", False)

        # Extract poster_url from images array gracefully.
        poster_url: str | None = None
        images: list = movie_data.get("images") or []
        for img in images:
            if img.get("coverType") == "poster":
                poster_url = img.get("remoteUrl") or img.get("url")
                break

        existing = (
            await session.exec(select(LibraryItem).where(LibraryItem.tmdb_id == tmdb_id))
        ).first()

        if existing is None:
            new_item = LibraryItem(
                tmdb_id=tmdb_id,
                radarr_movie_id=radarr_movie_id,
                title=title,
                year=year,
                overview=overview,
                poster_url=poster_url,
                radarr_has_file=has_file,
                status="in_library" if has_file else "idle",
            )
            session.add(new_item)
            logger.info(
                "MovieAdded: inserted LibraryItem tmdb_id=%d title=%r status=%s",
                tmdb_id, title, new_item.status,
            )
        else:
            # Link the Concierge record to Radarr if it was added outside Concierge.
            if existing.radarr_movie_id is None and radarr_movie_id is not None:
                existing.radarr_movie_id = radarr_movie_id
                logger.info(
                    "MovieAdded: linked existing LibraryItem id=%d to radarr_movie_id=%d",
                    existing.id, radarr_movie_id,
                )
            else:
                logger.info(
                    "MovieAdded: LibraryItem tmdb_id=%d already present and linked — no-op",
                    tmdb_id,
                )
            existing.updated_at = datetime.now(timezone.utc)

        await session.commit()
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # MovieDelete — remove LibraryItem unless an add/grab is in-flight   #
    # ------------------------------------------------------------------ #

    elif event_type == "MovieDelete":
        radarr_movie_id = movie_data.get("id")

        # Prefer lookup by tmdb_id; fall back to radarr_movie_id.
        item = None
        if tmdb_id:
            item = (
                await session.exec(select(LibraryItem).where(LibraryItem.tmdb_id == tmdb_id))
            ).first()
        if item is None and radarr_movie_id is not None:
            item = (
                await session.exec(
                    select(LibraryItem).where(LibraryItem.radarr_movie_id == radarr_movie_id)
                )
            ).first()

        if item is None:
            logger.info(
                "MovieDelete ignored: no LibraryItem found for tmdb_id=%s radarr_movie_id=%s",
                tmdb_id, radarr_movie_id,
            )
            return {"ok": True}

        # Guard: skip delete while an add sequence is still in flight.
        if item.status in ("grabbing", "downloading"):
            logger.warning(
                "MovieDelete skipped: LibraryItem id=%d is in-flight (status=%s)",
                item.id, item.status,
            )
            return {"ok": True}

        logger.info(
            "MovieDelete: deleting LibraryItem id=%d tmdb_id=%d title=%r",
            item.id, item.tmdb_id, item.title,
        )
        await session.delete(item)
        await session.commit()
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # MovieFileDelete — file removed; keep row, reset to idle            #
    # ------------------------------------------------------------------ #

    elif event_type == "MovieFileDelete":
        if not tmdb_id:
            logger.info("MovieFileDelete ignored: no tmdb_id in payload")
            return {"ok": True}

        item = (
            await session.exec(select(LibraryItem).where(LibraryItem.tmdb_id == tmdb_id))
        ).first()

        if item is None:
            logger.info(
                "MovieFileDelete ignored: no LibraryItem with tmdb_id=%d", tmdb_id
            )
            return {"ok": True}

        logger.info(
            "MovieFileDelete: transitioning LibraryItem id=%d from status=%s to idle",
            item.id, item.status,
        )
        item.status = "idle"
        item.radarr_has_file = False
        item.chosen_release_title = None
        item.chosen_release_size_gb = None
        item.chosen_release_quality = None
        item.download_id = None
        item.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # All other / unknown event types                                     #
    # ------------------------------------------------------------------ #

    else:
        logger.info("Webhook ignored: unhandled eventType=%s", event_type)
        return {"status": "ignored"}


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
