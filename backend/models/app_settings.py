import json
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

_DEFAULT_AVOID_KEYWORDS = '["BRRip","CAM","TS","HDCAM"]'


class AppSettings(SQLModel, table=True):
    """Single-row table for user-editable scoring preferences.

    Seeded from .env defaults on first startup. Changes take effect immediately
    without a server restart.
    """

    __tablename__ = "app_settings"

    id: int | None = Field(default=None, primary_key=True)
    max_size_gb: float = 40.0
    preferred_quality: str = "2160p"
    avoid_keywords_json: str = Field(default=_DEFAULT_AVOID_KEYWORDS)
    fcm_token: str | None = Field(default=None)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AppSettingsRead(SQLModel):
    max_size_gb: float
    preferred_quality: str
    avoid_keywords: list[str]
    fcm_token: str | None = None
    updated_at: datetime


class AppSettingsUpdate(SQLModel):
    max_size_gb: float | None = None
    preferred_quality: str | None = None
    avoid_keywords: list[str] | None = None
    fcm_token: str | None = None


def to_read(s: AppSettings) -> AppSettingsRead:
    return AppSettingsRead(
        max_size_gb=s.max_size_gb,
        preferred_quality=s.preferred_quality,
        avoid_keywords=json.loads(s.avoid_keywords_json),
        fcm_token=s.fcm_token,
        updated_at=s.updated_at,
    )
