"""Reconcile the Concierge LibraryItem table with the Radarr movie catalogue.

Radarr is the source of truth for whether a movie exists. This module provides
a single async function, ``reconcile_with_radarr``, that performs a bi-directional
sync between the two systems:

- Radarr-only movies are INSERTed into the local DB.
- Concierge-only rows that have a ``radarr_movie_id`` (i.e. we added them) but
  are no longer present in Radarr are DELETEd, unless they are in-flight.
- Both-sides rows have their metadata kept current and their ``radarr_has_file``
  / status field refreshed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.config import Settings, get_settings
from backend.models.library_item import LibraryItem
from backend.services.radarr import list_movies

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Statuses that represent in-flight add/download flows.  We must not DELETE a
# LibraryItem in one of these states even if Radarr reports it absent, because
# the add or download round-trip may not have completed yet.
_IN_FLIGHT_STATUSES: frozenset[str] = frozenset({"grabbing", "downloading"})


def _extract_poster_url(images: list[dict]) -> str | None:
    """Return the ``remoteUrl`` of the first image whose ``coverType`` is ``"poster"``.

    Radarr's ``images`` array contains objects like::

        {
            "coverType": "poster",
            "url": "/MediaCover/1/poster.jpg?...",
            "remoteUrl": "https://image.tmdb.org/t/p/original/..."
        }

    The ``remoteUrl`` key is the publicly-reachable TMDB URL and is what we
    store.  Falls back to ``None`` if the array is absent, empty, or contains
    no poster entry.
    """
    for image in images or []:
        if image.get("coverType") == "poster":
            remote = image.get("remoteUrl")
            if remote:
                return str(remote)
    return None


async def reconcile_with_radarr(
    session: AsyncSession,
    settings: Settings | None = None,
) -> None:
    """Bi-directional sync between the Concierge ``LibraryItem`` table and Radarr.

    Args:
        session:  An open ``AsyncSession`` (caller owns lifecycle / commit).
        settings: Optional pre-built ``Settings`` instance.  If ``None``,
                  ``get_settings()`` is called (respects ``@lru_cache``).

    Raises:
        RadarrError: Propagated directly — caller decides how to handle.
    """
    if settings is None:
        settings = get_settings()

    # ------------------------------------------------------------------
    # 1. Fetch both sides
    # ------------------------------------------------------------------
    radarr_movies: list[dict] = await list_movies(settings)
    result = await session.exec(select(LibraryItem))
    db_items: list[LibraryItem] = list(result.all())

    # Index by tmdb_id for O(1) lookup
    radarr_by_tmdb: dict[int, dict] = {
        int(m["tmdbId"]): m for m in radarr_movies if m.get("tmdbId")
    }
    db_by_tmdb: dict[int, LibraryItem] = {item.tmdb_id: item for item in db_items}

    now = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 2. Radarr-only: INSERT
    # ------------------------------------------------------------------
    radarr_only_tmdb_ids = radarr_by_tmdb.keys() - db_by_tmdb.keys()
    for tmdb_id in radarr_only_tmdb_ids:
        movie = radarr_by_tmdb[tmdb_id]
        has_file: bool = bool(movie.get("hasFile", False))
        status = "in_library" if has_file else "idle"
        poster_url = _extract_poster_url(movie.get("images", []))

        new_item = LibraryItem(
            tmdb_id=tmdb_id,
            radarr_movie_id=int(movie["id"]),
            title=str(movie.get("title", "")),
            year=int(movie.get("year", 0)),
            overview=movie.get("overview") or None,
            poster_url=poster_url,
            status=status,
            radarr_has_file=has_file,
            created_at=now,
            updated_at=now,
        )
        session.add(new_item)
        logger.info(
            "sync: INSERT LibraryItem tmdb_id=%d title=%r radarr_id=%d status=%s",
            tmdb_id,
            new_item.title,
            new_item.radarr_movie_id,
            status,
        )

    # ------------------------------------------------------------------
    # 3. Concierge-only (with radarr_movie_id set): DELETE unless in-flight
    # ------------------------------------------------------------------
    concierge_only_tmdb_ids = db_by_tmdb.keys() - radarr_by_tmdb.keys()
    for tmdb_id in concierge_only_tmdb_ids:
        item = db_by_tmdb[tmdb_id]

        # Only delete rows that we previously registered in Radarr.
        # Rows without a radarr_movie_id were never sent to Radarr
        # (e.g. a failed add), so we leave them for the caller to handle.
        if item.radarr_movie_id is None:
            continue

        # Guard: do not delete while a download is in flight.
        if item.status in _IN_FLIGHT_STATUSES:
            logger.warning(
                "sync: SKIP delete tmdb_id=%d title=%r — status is %r (in-flight)",
                tmdb_id,
                item.title,
                item.status,
            )
            continue

        await session.delete(item)
        logger.info(
            "sync: DELETE LibraryItem tmdb_id=%d title=%r (no longer in Radarr)",
            tmdb_id,
            item.title,
        )

    # ------------------------------------------------------------------
    # 4. Both sides: UPDATE metadata + radarr_has_file / status
    # ------------------------------------------------------------------
    both_tmdb_ids = db_by_tmdb.keys() & radarr_by_tmdb.keys()
    for tmdb_id in both_tmdb_ids:
        item = db_by_tmdb[tmdb_id]
        movie = radarr_by_tmdb[tmdb_id]

        changed = False

        # -- Metadata fields --
        new_title = str(movie.get("title", ""))
        if new_title and new_title != item.title:
            logger.info(
                "sync: UPDATE tmdb_id=%d title %r -> %r",
                tmdb_id,
                item.title,
                new_title,
            )
            item.title = new_title
            changed = True

        new_year = int(movie.get("year", 0))
        if new_year and new_year != item.year:
            logger.info(
                "sync: UPDATE tmdb_id=%d year %d -> %d",
                tmdb_id,
                item.year,
                new_year,
            )
            item.year = new_year
            changed = True

        new_overview: str | None = movie.get("overview") or None
        if new_overview != item.overview:
            logger.info("sync: UPDATE tmdb_id=%d overview changed", tmdb_id)
            item.overview = new_overview
            changed = True

        new_poster_url = _extract_poster_url(movie.get("images", []))
        if new_poster_url != item.poster_url:
            logger.info(
                "sync: UPDATE tmdb_id=%d poster_url changed -> %r",
                tmdb_id,
                new_poster_url,
            )
            item.poster_url = new_poster_url
            changed = True

        # -- radarr_has_file (always refresh) --
        new_has_file: bool = bool(movie.get("hasFile", False))
        if new_has_file != item.radarr_has_file:
            logger.info(
                "sync: UPDATE tmdb_id=%d radarr_has_file %s -> %s",
                tmdb_id,
                item.radarr_has_file,
                new_has_file,
            )
            item.radarr_has_file = new_has_file
            changed = True

        # -- Status transitions driven by radarr_has_file --
        if new_has_file and item.status == "idle":
            logger.info(
                "sync: UPDATE tmdb_id=%d status idle -> in_library (has file now)",
                tmdb_id,
            )
            item.status = "in_library"
            changed = True
        elif not new_has_file and item.status == "in_library":
            logger.info(
                "sync: UPDATE tmdb_id=%d status in_library -> idle (file removed)",
                tmdb_id,
            )
            item.status = "idle"
            # Clear release/download metadata — no longer applicable
            item.chosen_release_title = None
            item.chosen_release_size_gb = None
            item.chosen_release_quality = None
            item.download_id = None
            changed = True

        if changed:
            item.updated_at = now
            session.add(item)

    await session.commit()
    logger.info(
        "sync: reconcile complete — inserted=%d deleted_eligible=%d updated=%d",
        len(radarr_only_tmdb_ids),
        # Count only deletable (radarr_movie_id set, not in-flight)
        sum(
            1
            for tid in concierge_only_tmdb_ids
            if db_by_tmdb[tid].radarr_movie_id is not None
            and db_by_tmdb[tid].status not in _IN_FLIGHT_STATUSES
        ),
        len(both_tmdb_ids),
    )
