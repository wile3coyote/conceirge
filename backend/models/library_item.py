from datetime import datetime, timezone
from typing import Literal

from sqlmodel import Field, SQLModel

LibraryStatus = Literal[
    "searching", "grabbing", "downloading", "downloaded", "in_library", "failed"
]


class LibraryItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tmdb_id: int = Field(index=True)
    radarr_movie_id: int | None = Field(default=None)
    title: str
    year: int
    overview: str | None = None
    poster_url: str | None = None
    status: str = "searching"
    fail_reason: str | None = None
    chosen_release_title: str | None = None
    chosen_release_size_gb: float | None = None
    chosen_release_quality: str | None = None
    download_id: str | None = None  # SABnzbd nzo_id, stored from Radarr Grab webhook
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LibraryItemRead(SQLModel):
    """API response model — includes all LibraryItem fields plus transient download_progress."""

    id: int | None = None
    tmdb_id: int
    radarr_movie_id: int | None = None
    title: str
    year: int
    overview: str | None = None
    poster_url: str | None = None
    status: str
    fail_reason: str | None = None
    chosen_release_title: str | None = None
    chosen_release_size_gb: float | None = None
    chosen_release_quality: str | None = None
    download_id: str | None = None
    download_progress: float | None = None  # fetched live from SABnzbd, never persisted
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
