import httpx

from backend.config import Settings
from backend.exceptions import JellyfinError


async def refresh_library(settings: Settings) -> None:
    """POST /Library/Refresh — trigger a full Jellyfin library scan."""
    api_key = settings.jellyfin_api_key.get_secret_value()
    if not api_key:
        raise JellyfinError("Jellyfin API key is not configured", code="config_error")

    url = f"{settings.jellyfin_url}/Library/Refresh"
    headers = {"X-Emby-Token": api_key}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)
    except httpx.RequestError as exc:
        raise JellyfinError(f"Jellyfin unreachable: {exc}", code="jellyfin_error") from exc

    if not response.is_success:
        raise JellyfinError(
            f"Jellyfin refresh failed with status {response.status_code}",
            code="jellyfin_error",
        )
