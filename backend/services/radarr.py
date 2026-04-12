import asyncio

import httpx

from backend.config import Settings
from backend.exceptions import RadarrError


def _base_url(settings: Settings) -> str:
    return f"{settings.radarr_url}/api/v3"


def _headers(settings: Settings) -> dict[str, str]:
    api_key = settings.radarr_api_key.get_secret_value()
    if not api_key:
        raise RadarrError("Radarr API key is not configured", code="config_error")
    return {"X-Api-Key": api_key}


async def lookup_movie(
    query: str, settings: Settings, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """GET /api/v3/movie/lookup — returns raw list of Radarr movie dicts."""
    url = f"{_base_url(settings)}/movie/lookup"
    try:
        if client is not None:
            response = await client.get(url, headers=_headers(settings), params={"term": query})
        else:
            async with httpx.AsyncClient() as c:
                response = await c.get(url, headers=_headers(settings), params={"term": query})
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr lookup failed with status {response.status_code}",
            code="radarr_error",
        )

    return response.json()


async def get_quality_profile_id(
    settings: Settings, client: httpx.AsyncClient | None = None
) -> int:
    """GET /api/v3/qualityprofile — returns the id of the first profile."""
    url = f"{_base_url(settings)}/qualityprofile"
    try:
        if client is not None:
            response = await client.get(url, headers=_headers(settings))
        else:
            async with httpx.AsyncClient() as c:
                response = await c.get(url, headers=_headers(settings))
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr quality profile fetch failed with status {response.status_code}"
        )

    profiles: list[dict] = response.json()
    if not profiles:
        raise RadarrError("No quality profiles found in Radarr")

    return int(profiles[0]["id"])


async def get_root_folder(
    settings: Settings, client: httpx.AsyncClient | None = None
) -> str:
    """GET /api/v3/rootfolder — returns the path of the first folder."""
    url = f"{_base_url(settings)}/rootfolder"
    try:
        if client is not None:
            response = await client.get(url, headers=_headers(settings))
        else:
            async with httpx.AsyncClient() as c:
                response = await c.get(url, headers=_headers(settings))
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr root folder fetch failed with status {response.status_code}"
        )

    folders: list[dict] = response.json()
    if not folders:
        raise RadarrError("No root folders configured in Radarr")

    return str(folders[0]["path"])


async def add_movie(
    tmdb_id: int,
    title: str,
    year: int,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """POST /api/v3/movie — adds a movie to Radarr and returns the created movie dict."""
    quality_profile_id = await get_quality_profile_id(settings, client=client)
    root_folder_path = await get_root_folder(settings, client=client)

    url = f"{_base_url(settings)}/movie"
    payload = {
        "tmdbId": tmdb_id,
        "title": title,
        "year": year,
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder_path,
        "monitored": True,
        "minimumAvailability": "announced",
        "addOptions": {"searchForMovie": False},
    }

    try:
        if client is not None:
            response = await client.post(url, headers=_headers(settings), json=payload)
        else:
            async with httpx.AsyncClient() as c:
                response = await c.post(url, headers=_headers(settings), json=payload)
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr add movie failed with status {response.status_code}"
        )

    return response.json()


async def trigger_release_search(
    movie_id: int, settings: Settings, client: httpx.AsyncClient | None = None
) -> None:
    """POST /api/v3/command — triggers a MovieSearch command in Radarr."""
    url = f"{_base_url(settings)}/command"
    payload = {"name": "MovieSearch", "movieIds": [movie_id]}

    try:
        if client is not None:
            response = await client.post(url, headers=_headers(settings), json=payload)
        else:
            async with httpx.AsyncClient() as c:
                response = await c.post(url, headers=_headers(settings), json=payload)
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr trigger search failed with status {response.status_code}"
        )


async def grab_release(
    guid: str, indexer_id: int, settings: Settings, client: httpx.AsyncClient | None = None
) -> None:
    """POST /api/v3/release — tells Radarr to grab a specific release."""
    url = f"{_base_url(settings)}/release"
    payload = {"guid": guid, "indexerId": indexer_id}

    try:
        if client is not None:
            response = await client.post(url, headers=_headers(settings), json=payload)
        else:
            async with httpx.AsyncClient(timeout=60.0) as c:
                response = await c.post(url, headers=_headers(settings), json=payload)
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr grab failed with status {response.status_code}",
            code="radarr_error",
        )


async def fetch_releases(
    movie_id: int, settings: Settings, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """GET /api/v3/release — returns raw list of release dicts for a movie."""
    url = f"{_base_url(settings)}/release"

    try:
        if client is not None:
            response = await client.get(
                url, headers=_headers(settings), params={"movieId": movie_id}
            )
        else:
            async with httpx.AsyncClient() as c:
                response = await c.get(
                    url, headers=_headers(settings), params={"movieId": movie_id}
                )
    except httpx.RequestError as exc:
        raise RadarrError(f"Radarr unreachable: {exc}") from exc

    if not response.is_success:
        raise RadarrError(
            f"Radarr fetch releases failed with status {response.status_code}"
        )

    return response.json()


async def search_movie_releases(query: str, settings: Settings) -> tuple[dict, list[dict]]:
    """Orchestrate the full flow: lookup → add if needed → trigger search → poll releases."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        results = await lookup_movie(query, settings, client=client)
        if not results:
            raise RadarrError("No results found for query")

        movie: dict = results[0]

        # movie["id"] > 0 means it already exists in Radarr
        if movie.get("id", 0) <= 0:
            try:
                tmdb_id = movie["tmdbId"]
                title = movie["title"]
                year = movie["year"]
            except KeyError as exc:
                raise RadarrError(f"Radarr lookup result missing field: {exc}") from exc

            movie = await add_movie(
                tmdb_id=tmdb_id,
                title=title,
                year=year,
                settings=settings,
                client=client,
            )
            # Give Radarr a moment to finish indexing the newly-added movie
            # before firing MovieSearch — avoids a race condition that causes 500.
            await asyncio.sleep(2)

        movie_id: int = movie["id"]

        # GET /api/v3/release triggers an interactive indexer search and returns
        # results in one call — no need for a separate MovieSearch command.
        releases: list[dict] = []
        for attempt in range(5):
            releases = await fetch_releases(movie_id, settings, client=client)
            if releases:
                break
            if attempt < 4:
                await asyncio.sleep(2)

    return movie, releases
