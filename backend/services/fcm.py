import asyncio
import logging

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

_FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


async def send_download_complete(
    project_id: str,
    service_account_path: str,
    fcm_token: str,
    title: str,
    year: int,
    tmdb_id: int,
    quality: str | None,
) -> None:
    creds = service_account.Credentials.from_service_account_file(
        service_account_path, scopes=_FCM_SCOPES
    )
    await asyncio.to_thread(creds.refresh, Request())

    body = f"{title} ({year})"
    if quality:
        body += f" · {quality}"
    body += " is ready in your library"

    payload = {
        "message": {
            "token": fcm_token,
            "notification": {"title": "Download complete", "body": body},
            "data": {"screen": "library", "tmdb_id": str(tmdb_id)},
        }
    }

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        resp.raise_for_status()
