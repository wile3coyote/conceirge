from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class DownloadStatus(str, Enum):
    pending = "pending"
    searching = "searching"
    grabbed = "grabbed"
    complete = "complete"
    failed = "failed"


class Download(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    radarr_movie_id: int
    movie_title: str
    year: int
    status: DownloadStatus
    chosen_release_title: str | None = Field(default=None)
    chosen_release_size_gb: float | None = Field(default=None)
    chosen_release_quality: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
