from pydantic import BaseModel


class ScoredRelease(BaseModel):
    title: str
    size_gb: float
    quality: str
    score: int
    rejected: bool
    reject_reason: str | None = None
    radarr_guid: str
