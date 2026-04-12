from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ScoredRelease(BaseModel):
    title: str
    size_gb: float
    quality: str
    score: int
    rejected: bool
    reject_reason: str | None = None
    radarr_guid: str
    indexer_id: int = 0


class MovieSearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MovieSearchResponse(BaseModel):
    radarr_movie_id: int
    title: str
    year: int
    overview: str | None = None
    poster_url: str | None = None  # extracted from Radarr images list (coverType == "poster")
    tmdb_id: int
    releases: list[ScoredRelease]


class GrabRequest(BaseModel):
    radarr_movie_id: int
    movie_title: str
    year: int
