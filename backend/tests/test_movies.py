"""Integration tests for POST /movies/search (returns movie info only, no releases)."""

import httpx
import pytest
import respx
from httpx import Response


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


@pytest.mark.asyncio
async def test_search_returns_movie_list(async_client):
    """Search returns a list of MovieSearchResult dicts with no releases field."""
    movie = make_radarr_movie()

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        response = await async_client.post("/movies/search", json={"query": "Inception"})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    result = body[0]
    assert result["tmdb_id"] == 12345
    assert result["title"] == "Inception"
    assert result["year"] == 2010
    assert "releases" not in result


@pytest.mark.asyncio
async def test_search_returns_up_to_five_results(async_client):
    """Search caps results at 5 even if Radarr returns more."""
    movies = [make_radarr_movie(movie_id=i, tmdb_id=i) for i in range(1, 8)]

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=movies)
        )
        response = await async_client.post("/movies/search", json={"query": "Movie"})

    assert response.status_code == 200
    assert len(response.json()) == 5


@pytest.mark.asyncio
async def test_search_poster_url_extracted(async_client):
    """poster_url is extracted from the Radarr images list (coverType == 'poster')."""
    movie = make_radarr_movie()

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[movie])
        )
        response = await async_client.post("/movies/search", json={"query": "Inception"})

    assert response.status_code == 200
    assert response.json()[0]["poster_url"] == "http://img.test/poster.jpg"


@pytest.mark.asyncio
async def test_search_no_results_returns_502(async_client):
    """Empty Radarr lookup → RadarrError raised → 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(200, json=[])
        )
        response = await async_client.post("/movies/search", json={"query": "NoFilm"})

    assert response.status_code == 502
    assert response.json()["code"] == "radarr_error"


@pytest.mark.asyncio
async def test_search_radarr_unreachable_returns_502(async_client):
    """Connection error to Radarr → 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            side_effect=httpx.ConnectError("refused")
        )
        response = await async_client.post("/movies/search", json={"query": "Inception"})

    assert response.status_code == 502
    assert response.json()["code"] == "radarr_error"


@pytest.mark.asyncio
async def test_search_radarr_500_returns_502(async_client):
    """Radarr returns 500 → 502."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://radarr.test/api/v3/movie/lookup").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        response = await async_client.post("/movies/search", json={"query": "Inception"})

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_search_blank_query_returns_422(async_client):
    """Empty string query fails min_length=1 validation → 422."""
    response = await async_client.post("/movies/search", json={"query": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_missing_query_returns_422(async_client):
    """Missing 'query' field → 422."""
    response = await async_client.post("/movies/search", json={})
    assert response.status_code == 422
