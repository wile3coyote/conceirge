import logging

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)


async def get_queue_progress_map(settings: Settings) -> dict[str, float]:
    """Return a mapping of SABnzbd nzo_id -> percentage complete for all active downloads.

    Returns an empty dict if SABnzbd is not configured or unreachable.
    """
    if not settings.sabnzbd_url or not settings.sabnzbd_api_key.get_secret_value():
        return {}

    url = f"{settings.sabnzbd_url}/api"
    params = {
        "mode": "queue",
        "output": "json",
        "apikey": settings.sabnzbd_api_key.get_secret_value(),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
        if not response.is_success:
            logger.warning("SABnzbd queue request failed: HTTP %s", response.status_code)
            return {}
        slots: list[dict] = response.json().get("queue", {}).get("slots", [])
        return {
            slot["nzo_id"]: float(slot.get("percentage", "0"))
            for slot in slots
            if "nzo_id" in slot
        }
    except Exception:
        logger.exception("Failed to fetch SABnzbd queue")
        return {}
