from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    radarr_url: str = "http://localhost:7878"
    radarr_api_key: SecretStr = SecretStr("")
    jellyfin_url: str = "http://localhost:8096"
    jellyfin_api_key: SecretStr = SecretStr("")
    sabnzbd_url: str = "http://localhost:8080"
    sabnzbd_api_key: SecretStr = SecretStr("")
    firebase_service_account_path: str = "firebase-service-account.json"
    firebase_project_id: str = ""
    max_size_gb: float = 40.0
    max_size_tolerance_pct: float = 20.0  # % over max_size_gb still accepted
    preferred_quality: str = "2160p"
    avoid_keywords: list[str] = ["BRRip", "CAM", "TS", "HDCAM"]

    @field_validator("avoid_keywords", mode="before")
    @classmethod
    def _parse_keywords(cls, v: object) -> object:
        if isinstance(v, str):
            # Accept both JSON arrays and comma-separated strings
            stripped = v.strip()
            if stripped.startswith("["):
                import json
                return json.loads(stripped)
            return [s.strip() for s in stripped.split(",") if s.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
