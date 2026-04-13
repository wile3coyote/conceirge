import asyncio
import logging
from datetime import datetime, timezone

import httpx

from backend.config import Settings
from backend.database import async_session
from backend.exceptions import ConciergeError, RadarrError
from backend.models.library_item import LibraryItem
from backend.services import radarr, scorer

logger = logging.getLogger(__name__)


async def run_library_pipeline(item_id: int, settings: Settings) -> None:
    """Background task: Radarr lookup → fetch releases → score → grab best."""
    async with async_session() as session:
        item = await session.get(LibraryItem, item_id)
        if item is None:
            return

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Step 1: ensure movie is in Radarr
                if item.radarr_movie_id is None:
                    results = await radarr.lookup_movie(
                        f"tmdb:{item.tmdb_id}", settings, client=client
                    )
                    if not results:
                        raise RadarrError(
                            f"Movie tmdb_id={item.tmdb_id} not found via Radarr lookup"
                        )
                    movie = results[0]
                    if movie.get("id", 0) <= 0:
                        movie = await radarr.add_movie(
                            tmdb_id=item.tmdb_id,
                            title=item.title,
                            year=item.year,
                            settings=settings,
                            client=client,
                        )
                        await asyncio.sleep(2)

                    item.radarr_movie_id = movie["id"]
                    item.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(item)

                # Step 2: fetch releases with retry
                assert item.radarr_movie_id is not None
                radarr_movie_id: int = item.radarr_movie_id
                releases: list[dict] = []
                for attempt in range(5):
                    releases = await radarr.fetch_releases(
                        radarr_movie_id, settings, client=client
                    )
                    if releases:
                        break
                    if attempt < 4:
                        await asyncio.sleep(2)

                scored = scorer.score_releases(releases, settings)
                best = next((r for r in scored if not r.rejected), None)

                if best is None:
                    item.status = "failed"
                    item.fail_reason = "No acceptable releases found"
                    item.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    return

                # Step 3: grab – commit status BEFORE calling Radarr to avoid
                # race with the Grab webhook Radarr fires immediately after accepting
                item.status = "grabbing"
                item.chosen_release_title = best.title
                item.chosen_release_size_gb = best.size_gb
                item.chosen_release_quality = best.quality
                item.updated_at = datetime.now(timezone.utc)
                await session.commit()
                await session.refresh(item)

                await radarr.grab_release(
                    best.radarr_guid, best.indexer_id, settings, client=client
                )

        except ConciergeError as exc:
            await session.refresh(item)
            if item.status in ("searching", "grabbing"):
                item.status = "failed"
                item.fail_reason = exc.detail
                item.updated_at = datetime.now(timezone.utc)
                await session.commit()
            logger.exception("Library pipeline failed for item %d: %s", item_id, exc.detail)
        except Exception as exc:
            await session.refresh(item)
            if item.status in ("searching", "grabbing"):
                item.status = "failed"
                item.fail_reason = str(exc)
                item.updated_at = datetime.now(timezone.utc)
                await session.commit()
            logger.exception("Unexpected error in library pipeline for item %d", item_id)
