from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from backend.config import Settings, get_settings
from backend.database import get_session
from backend.exceptions import RadarrError
from backend.models.download import Download, DownloadStatus
from backend.models.release import GrabRequest, MovieSearchRequest, MovieSearchResponse, ScoredRelease
from backend.services import radarr, scorer

router = APIRouter(prefix="/movies", tags=["movies"])


def _extract_poster_url(images: list[dict]) -> str | None:
    """Return remoteUrl for the poster image, or None if not present."""
    for image in images:
        if image.get("coverType") == "poster":
            return image.get("remoteUrl")
    return None


@router.post("/search", response_model=MovieSearchResponse)
async def search_movies(
    request: MovieSearchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MovieSearchResponse:
    """Search for a movie in Radarr, trigger a release search, and return scored releases."""
    movie, releases = await radarr.search_movie_releases(request.query, settings)

    scored: list[ScoredRelease] = scorer.score_releases(releases, settings)

    return MovieSearchResponse(
        radarr_movie_id=movie["id"],
        title=movie["title"],
        year=movie["year"],
        overview=movie.get("overview"),
        poster_url=_extract_poster_url(movie.get("images") or []),
        tmdb_id=movie["tmdbId"],
        releases=scored,
    )


@router.post("/grab", response_model=Download, status_code=201)
async def grab_movie(
    request: GrabRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Download:
    """Fetch releases for the movie, pick the best one, and tell Radarr to grab it."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        releases = await radarr.fetch_releases(request.radarr_movie_id, settings, client=client)
        scored = scorer.score_releases(releases, settings)

        best = next((r for r in scored if not r.rejected), None)
        if best is None:
            raise RadarrError(
                "No acceptable releases found for this movie",
                code="no_releases",
            )

        await radarr.grab_release(best.radarr_guid, best.indexer_id, settings, client=client)

    download = Download(
        radarr_movie_id=request.radarr_movie_id,
        movie_title=request.movie_title,
        year=request.year,
        status=DownloadStatus.grabbed,
        chosen_release_title=best.title,
        chosen_release_size_gb=best.size_gb,
        chosen_release_quality=best.quality,
    )
    session.add(download)
    await session.commit()
    await session.refresh(download)
    return download
