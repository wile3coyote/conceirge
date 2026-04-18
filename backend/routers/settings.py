import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.models.app_settings import AppSettings, AppSettingsRead, AppSettingsUpdate, to_read

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_settings(session: AsyncSession) -> AppSettings:
    """Return the single settings row, raising 500 if it doesn't exist (should be seeded at startup)."""
    row = (await session.exec(select(AppSettings))).first()
    if row is None:
        # Fallback: create with defaults (shouldn't happen after proper startup)
        row = AppSettings()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@router.get("", response_model=AppSettingsRead)
async def get_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppSettingsRead:
    """Return the current user-configurable scoring settings."""
    return to_read(await _get_settings(session))


@router.put("", response_model=AppSettingsRead)
async def update_settings(
    body: AppSettingsUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppSettingsRead:
    """Update scoring settings. Only supplied fields are changed."""
    row = await _get_settings(session)

    if body.max_size_gb is not None:
        row.max_size_gb = body.max_size_gb
    if body.preferred_quality is not None:
        row.preferred_quality = body.preferred_quality
    if body.avoid_keywords is not None:
        row.avoid_keywords_json = json.dumps(body.avoid_keywords)
    if body.fcm_token is not None:
        row.fcm_token = body.fcm_token if body.fcm_token != "" else None
    row.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(row)
    return to_read(row)
