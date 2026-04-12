"""Integration tests for POST /movies/search.

All HTTP calls that radarr.py makes are intercepted by respx.  asyncio.sleep
inside the polling loop is patched out so tests run instantly.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from httpx import Response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radarr_movie(
    movie_id: int = 1,
    tmdb_id: int = 12345,
    title: str = "Inception",
    year: int = 2010,
    exists: bool = True,
) -> dict:
    return {
        "id": movie_id if exists else 0,
        "tmdbId": tmdb_id,
        "title": title,
        "year": year,
        "overview": "A thief who steals corporate secrets.",
        "images": [{"coverType": "poster", "remoteUrl": "http://img.test/poster.jpg"}],
    }


def make_radarr_release(
    guid: str = "r1",
    title: str = "Inception.2010.2160p.BluRay",
    size: int = 15 * 1024**3,
    resolution: int = 2160,
) -> dict:
    return {
        "guid": guid,
        "title": title,
        "size": size,
        "quality": {"quality": {"name": "Bluray-2160p", "resolution": resolution}},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_movie_already_in_radarr(async_client):
    """Movie exists in Radarr (id > 0) — add_movie is skipped, releases returned."""
    movie = make_radarr_movie(exists=True)
    release = make_radarr_release()

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        mock.post("http://radarr.test/api/v3/command").mock(
            return_value=Response(202, json={"id": 1})
        )
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[release])
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Inception"
    assert body["radarr_movie_id"] == 1
    assert body["tmdb_id"] == 12345
    assert len(body["releases"]) == 1
    assert body["releases"][0]["rejected"] is False
    assert body["releases"][0]["quality"] == "2160p"


@pytest.mark.asyncio
async def test_search_movie_not_in_radarr_adds_then_searches(async_client):
    """Movie not in Radarr (id == 0) — add_movie flow runs, result has correct id."""
    lookup_result = make_radarr_movie(exists=False)
    added_movie = make_radarr_movie(exists=True, movie_id=1)
    release = make_radarr_release()

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[lookup_result])
        )
        mock.get("http://radarr.test/api/v3/qualityprofile").mock(
            return_value=Response(200, json=[{"id": 5, "name": "HD"}])
        )
        mock.get("http://radarr.test/api/v3/rootfolder").mock(
            return_value=Response(200, json=[{"id": 1, "path": "/movies"}])
        )
        mock.post("http://radarr.test/api/v3/movie").mock(
            return_value=Response(201, json=added_movie)
        )
        mock.post("http://radarr.test/api/v3/command").mock(
            return_value=Response(202, json={"id": 1})
        )
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[release])
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 200
    body = response.json()
    assert body["radarr_movie_id"] == 1
    assert body["title"] == "Inception"
    assert len(body["releases"]) == 1


@pytest.mark.asyncio
async def test_search_no_lookup_results_returns_502(async_client):
    """Radarr lookup returns empty list — RadarrError raised, response is 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[])
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "NonExistentFilm"}
            )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "radarr_error"


@pytest.mark.asyncio
async def test_search_radarr_unreachable_returns_502(async_client):
    """Radarr lookup raises ConnectError — response is 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "radarr_error"


@pytest.mark.asyncio
async def test_search_releases_empty_after_all_polls(async_client):
    """Release endpoint always returns [] — response is 200 with empty releases list."""
    movie = make_radarr_movie(exists=True)

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        mock.post("http://radarr.test/api/v3/command").mock(
            return_value=Response(202, json={"id": 1})
        )
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[])
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 200
    body = response.json()
    assert body["releases"] == []


@pytest.mark.asyncio
async def test_search_poster_url_extracted_correctly(async_client):
    """poster_url is extracted from the Radarr images list for coverType=poster."""
    movie = make_radarr_movie(exists=True)
    release = make_radarr_release()

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        mock.post("http://radarr.test/api/v3/command").mock(
            return_value=Response(202, json={"id": 1})
        )
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[release])
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 200
    assert response.json()["poster_url"] == "http://img.test/poster.jpg"


@pytest.mark.asyncio
async def test_search_rejected_releases_included_in_response(async_client):
    """Rejected releases (720p) appear in the response list with rejected=True."""
    movie = make_radarr_movie(exists=True)
    releases = [
        make_radarr_release(guid="r-2160", title="Inception.2010.2160p.BluRay", resolution=2160),
        make_radarr_release(
            guid="r-720",
            title="Inception.2010.720p.BluRay",
            size=3 * 1024**3,
            resolution=720,
        ),
    ]

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        mock.post("http://radarr.test/api/v3/command").mock(
            return_value=Response(202, json={"id": 1})
        )
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=releases)
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 200
    body = response.json()
    result_releases = body["releases"]
    assert len(result_releases) == 2
    # Non-rejected first
    assert result_releases[0]["rejected"] is False
    assert result_releases[0]["radarr_guid"] == "r-2160"
    # Rejected at end
    assert result_releases[1]["rejected"] is True
    assert result_releases[1]["radarr_guid"] == "r-720"


@pytest.mark.asyncio
async def test_search_radarr_lookup_non_200_returns_502(async_client):
    """Radarr lookup returns a 500 — RadarrError raised, response is 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 502
    assert response.json()["code"] == "radarr_error"


@pytest.mark.asyncio
async def test_search_missing_query_field_returns_422(async_client):
    """Request body missing required 'query' field — FastAPI returns 422."""
    response = await async_client.post("/movies/search", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_blank_query_returns_422(async_client):
    """Empty string query fails min_length=1 validation — FastAPI returns 422."""
    response = await async_client.post("/movies/search", json={"query": ""})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_polling_exhausts_all_attempts(async_client):
    """Confirm asyncio.sleep is called for each polling attempt when releases stay empty."""
    movie = make_radarr_movie(exists=True)

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        mock.post("http://radarr.test/api/v3/command").mock(
            return_value=Response(202, json={"id": 1})
        )
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[])
        )

        sleep_mock = AsyncMock()
        with patch("asyncio.sleep", sleep_mock):
            response = await async_client.post(
                "/movies/search", json={"query": "Inception"}
            )

    assert response.status_code == 200
    # The polling loop in radarr.py runs up to 5 iterations
    assert sleep_mock.call_count == 4


# ---------------------------------------------------------------------------
# POST /movies/grab
# ---------------------------------------------------------------------------

_GRAB_PAYLOAD = {
    "radarr_movie_id": 1,
    "movie_title": "Inception",
    "year": 2010,
}

_GOOD_RELEASE = make_radarr_release(
    guid="best-guid",
    title="Inception.2010.2160p.BluRay",
    resolution=2160,
    size=15 * 1024**3,
)


@pytest.mark.asyncio
async def test_grab_success_returns_201_with_download(async_client):
    """Server fetches releases, picks the best, grabs it — returns 201 with Download fields."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[_GOOD_RELEASE])
        )
        mock.post("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json={})
        )

        response = await async_client.post("/movies/grab", json=_GRAB_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "grabbed"
    assert body["radarr_movie_id"] == 1
    assert body["movie_title"] == "Inception"
    assert body["chosen_release_title"] == "Inception.2010.2160p.BluRay"
    assert body["chosen_release_quality"] == "2160p"


@pytest.mark.asyncio
async def test_grab_creates_download_record(async_client):
    """The returned JSON has a non-null integer id — the DB row was persisted."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[_GOOD_RELEASE])
        )
        mock.post("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json={})
        )

        response = await async_client.post("/movies/grab", json=_GRAB_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert isinstance(body["id"], int)


@pytest.mark.asyncio
async def test_grab_no_acceptable_releases_returns_502(async_client):
    """All releases rejected (720p only) — endpoint returns 502 with code 'no_releases'."""
    bad_release = make_radarr_release(
        guid="low-guid", title="Inception.2010.720p.BluRay", resolution=720, size=2 * 1024**3
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[bad_release])
        )

        response = await async_client.post("/movies/grab", json=_GRAB_PAYLOAD)

    assert response.status_code == 502
    assert response.json()["code"] == "no_releases"


@pytest.mark.asyncio
async def test_grab_fetch_releases_fails_returns_502(async_client):
    """Radarr returns 500 on the release fetch — endpoint returns 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        response = await async_client.post("/movies/grab", json=_GRAB_PAYLOAD)

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_grab_radarr_grab_fails_returns_502(async_client):
    """Releases fetched OK but the grab POST returns 500 — endpoint returns 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[_GOOD_RELEASE])
        )
        mock.post("http://radarr.test/api/v3/release").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        response = await async_client.post("/movies/grab", json=_GRAB_PAYLOAD)

    assert response.status_code == 502
    assert response.json()["code"] == "radarr_error"


@pytest.mark.asyncio
async def test_grab_picks_highest_scored_release(async_client):
    """When multiple releases exist, server picks the 2160p one over 1080p."""
    release_1080 = make_radarr_release(
        guid="guid-1080", title="Inception.2010.1080p.BluRay", resolution=1080, size=8 * 1024**3
    )
    release_2160 = make_radarr_release(
        guid="guid-2160", title="Inception.2010.2160p.BluRay", resolution=2160, size=15 * 1024**3
    )

    grabbed_guids: list[str] = []

    def capture_grab(request: httpx.Request) -> Response:
        import json
        grabbed_guids.append(json.loads(request.content)["guid"])
        return Response(200, json={})

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/release").mock(
            return_value=Response(200, json=[release_1080, release_2160])
        )
        mock.post("http://radarr.test/api/v3/release").mock(side_effect=capture_grab)

        response = await async_client.post("/movies/grab", json=_GRAB_PAYLOAD)

    assert response.status_code == 201
    assert grabbed_guids == ["guid-2160"]


@pytest.mark.asyncio
async def test_grab_missing_movie_title_returns_422(async_client):
    """Request body without movie_title fails Pydantic validation — FastAPI returns 422."""
    payload = {k: v for k, v in _GRAB_PAYLOAD.items() if k != "movie_title"}
    response = await async_client.post("/movies/grab", json=payload)

    assert response.status_code == 422
