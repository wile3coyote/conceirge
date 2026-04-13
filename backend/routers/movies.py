from typing import Annotated

from fastapi import APIRouter, Depends

from backend.config import Settings, get_settings
from backend.exceptions import RadarrError
from backend.models.release import MovieSearchRequest, MovieSearchResult
from backend.services import radarr

router = APIRouter(prefix="/movies", tags=["movies"])


def _extract_poster_url(images: list[dict]) -> str | None:
    """Return remoteUrl for the poster image, or None if not present."""
    for image in images:
        if image.get("coverType") == "poster":
            return image.get("remoteUrl")
    return None


@router.post("/search", response_model=list[MovieSearchResult])
async def search_movies(
    request: MovieSearchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[MovieSearchResult]:
    """Look up movies in Radarr and return basic info (no releases) for the UI."""
    results = await radarr.lookup_movie(request.query, settings)
    if not results:
        raise RadarrError("No results found for query", code="radarr_error")
    return [
        MovieSearchResult(
            tmdb_id=movie["tmdbId"],
            title=movie["title"],
            year=movie["year"],
            overview=movie.get("overview"),
            poster_url=_extract_poster_url(movie.get("images") or []),
        )
        for movie in results[:5]
    ]
