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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
