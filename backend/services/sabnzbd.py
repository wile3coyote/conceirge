import logging

import httpx

from backend.config import Settings
from backend.exceptions import ConciergeError

logger = logging.getLogger(__name__)


class SabnzbdError(ConciergeError):
    code = "sabnzbd_error"


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


async def delete_queue_item(
    nzo_id: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Cancel and remove an active SABnzbd queue item by nzo_id.

    Raises SabnzbdError on HTTP failure or when SABnzbd reports status: false.
    """
    url = f"{settings.sabnzbd_url}/api"
    params = {
        "mode": "queue",
        "name": "delete",
        "value": nzo_id,
        "output": "json",
        "apikey": settings.sabnzbd_api_key.get_secret_value(),
    }

    async def _do_request(c: httpx.AsyncClient) -> None:
        response = await c.get(url, params=params)
        if not response.is_success:
            raise SabnzbdError(
                f"SABnzbd queue delete failed: HTTP {response.status_code}",
                code="sabnzbd_error",
            )
        data = response.json()
        if not data.get("status"):
            raise SabnzbdError(
                f"SABnzbd queue delete returned status=false for nzo_id={nzo_id}",
                code="sabnzbd_error",
            )

    try:
        if client is not None:
            await _do_request(client)
        else:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await _do_request(c)
    except SabnzbdError:
        raise
    except Exception as exc:
        raise SabnzbdError(
            f"Unexpected error deleting SABnzbd queue item {nzo_id}: {exc}",
            code="sabnzbd_error",
        ) from exc
