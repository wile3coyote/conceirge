import asyncio
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends

from backend.config import Settings, get_settings

router = APIRouter(prefix="/status", tags=["status"])


def _result(
    ok: bool,
    version: str | None = None,
    latency_ms: int | None = None,
    detail: str | None = None,
) -> dict:
    return {"ok": ok, "version": version, "latency_ms": latency_ms, "detail": detail}


async def _check_radarr(settings: Settings) -> dict:
    if not settings.radarr_api_key.get_secret_value():
        return _result(False, detail="API key not configured")
    url = f"{settings.radarr_url}/api/v3/system/status"
    headers = {"X-Api-Key": settings.radarr_api_key.get_secret_value()}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
        ms = int((time.monotonic() - t0) * 1000)
        if resp.is_success:
            return _result(True, version=resp.json().get("version"), latency_ms=ms)
        return _result(False, latency_ms=ms, detail=f"HTTP {resp.status_code}")
    except httpx.TimeoutException:
        return _result(False, detail="Timed out")
    except httpx.RequestError as exc:
        return _result(False, detail=str(exc))


async def _check_sabnzbd(settings: Settings) -> dict:
    if not settings.sabnzbd_api_key.get_secret_value():
        return _result(False, detail="API key not configured")
    url = f"{settings.sabnzbd_url}/api"
    params = {
        "mode": "version",
        "output": "json",
        "apikey": settings.sabnzbd_api_key.get_secret_value(),
    }
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
        ms = int((time.monotonic() - t0) * 1000)
        if resp.is_success:
            return _result(True, version=resp.json().get("version"), latency_ms=ms)
        return _result(False, latency_ms=ms, detail=f"HTTP {resp.status_code}")
    except httpx.TimeoutException:
        return _result(False, detail="Timed out")
    except httpx.RequestError as exc:
        return _result(False, detail=str(exc))


async def _check_jellyfin(settings: Settings) -> dict:
    if not settings.jellyfin_api_key.get_secret_value():
        return _result(False, detail="API key not configured")
    url = f"{settings.jellyfin_url}/System/Info"
    headers = {"X-Emby-Token": settings.jellyfin_api_key.get_secret_value()}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
        ms = int((time.monotonic() - t0) * 1000)
        if resp.is_success:
            return _result(True, version=resp.json().get("Version"), latency_ms=ms)
        return _result(False, latency_ms=ms, detail=f"HTTP {resp.status_code}")
    except httpx.TimeoutException:
        return _result(False, detail="Timed out")
    except httpx.RequestError as exc:
        return _result(False, detail=str(exc))


@router.get("")
async def get_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Ping Radarr, SABnzbd, and Jellyfin in parallel and return connection status for each."""
    radarr, sabnzbd, jellyfin = await asyncio.gather(
        _check_radarr(settings),
        _check_sabnzbd(settings),
        _check_jellyfin(settings),
    )
    return {"radarr": radarr, "sabnzbd": sabnzbd, "jellyfin": jellyfin}
