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


class MovieSearchResult(BaseModel):
    tmdb_id: int
    title: str
    year: int
    overview: str | None = None
    poster_url: str | None = None


class AddToLibraryRequest(BaseModel):
    tmdb_id: int
    title: str
    year: int
    overview: str | None = None
    poster_url: str | None = None
