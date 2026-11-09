import httpx
import pytest

from app.tmdb.client import TMDBClient
from app.tmdb.errors import (
    TMDBAuthError,
    TMDBError,
    TMDBNotFound,
    TMDBResponseError,
    TMDBUnavailable,
)


@pytest.mark.asyncio
async def test_search_uses_bearer_token_without_exposing_it_in_url():
    token = "secret-test-token"
    captured_requests = []

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)

        return httpx.Response(
            200,
            json={"results": []},
        )

    transport = httpx.MockTransport(fake_tmdb)
    client = TMDBClient(token=token, transport=transport)

    try:
        results = await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert results == []
    assert len(captured_requests) == 1

    request = captured_requests[0]

    assert request.headers["Authorization"] == f"Bearer {token}"
    assert "api_key" not in request.url.params
    assert token not in str(request.url)
    assert request.url.params["language"] == "en-US"
    assert request.url.params["query"] == "The Matrix"


@pytest.mark.asyncio
async def test_authentication_failure_is_not_retried():
    requests_made = 0

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1
        return httpx.Response(401, json={"status_message": "Unauthorized"})

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
    )

    try:
        with pytest.raises(TMDBAuthError):
            await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert requests_made == 1


@pytest.mark.asyncio
async def test_temporary_failure_retries_then_succeeds():
    requests_made = 0
    delays = []

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1

        if requests_made < 3:
            return httpx.Response(503)

        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 603,
                        "title": "The Matrix",
                        "original_title": "The Matrix",
                        "release_date": "1999-03-31",
                    }
                ]
            },
        )

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
        sleep=fake_sleep,
    )

    try:
        movies = await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert requests_made == 3
    assert delays == [0.1, 0.2]
    assert len(movies) == 1
    assert movies[0].id == 603
    assert movies[0].title == "The Matrix"


@pytest.mark.asyncio
async def test_temporary_failure_stops_after_three_attempts():
    requests_made = 0
    delays = []

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1
        return httpx.Response(503)

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
        sleep=fake_sleep,
    )

    try:
        with pytest.raises(TMDBUnavailable):
            await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert requests_made == 3
    assert delays == [0.1, 0.2]


@pytest.mark.asyncio
async def test_timeout_raises_tmdb_unavailable():
    requests_made = 0
    delays = []

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1
        raise httpx.ReadTimeout("Simulated timeout", request=request)

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
        sleep=fake_sleep,
    )

    try:
        with pytest.raises(TMDBUnavailable):
            await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert requests_made == 3
    assert delays == [0.1, 0.2]


@pytest.mark.asyncio
async def test_movie_not_found_raises_typed_error_without_retry():
    requests_made = 0

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1
        return httpx.Response(404, json={"status_message": "Not Found"})

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
    )

    try:
        with pytest.raises(TMDBNotFound):
            await client.get_movie(999999999)
    finally:
        await client.aclose()

    assert requests_made == 1


@pytest.mark.asyncio
async def test_invalid_movie_data_raises_response_error():
    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 603,
                "title": "The Matrix",
            },
        )

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
    )

    try:
        with pytest.raises(TMDBResponseError):
            await client.get_movie(603)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_raises_response_error():
    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="This is not valid JSON",
        )

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
    )

    try:
        with pytest.raises(TMDBResponseError):
            await client.get_movie(603)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error", "expected_attempts"),
    [
        (400, TMDBResponseError, 1),
        (429, TMDBUnavailable, 3),
        (500, TMDBUnavailable, 1),
        (502, TMDBUnavailable, 3),
        (504, TMDBUnavailable, 3),
    ],
)
async def test_http_errors_are_classified_correctly(
    status_code: int,
    expected_error: type[TMDBError],
    expected_attempts: int,
):
    requests_made = 0

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1
        return httpx.Response(status_code)

    async def fake_sleep(seconds: float) -> None:
        pass

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
        sleep=fake_sleep,
    )

    try:
        with pytest.raises(expected_error):
            await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert requests_made == expected_attempts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code",
    [400, 401, 404, 429, 500, 503],
)
async def test_tmdb_errors_never_expose_token(status_code: int):
    token = "super-secret-test-token"

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"status_message": f"Request failed with {token}"},
        )

    async def fake_sleep(seconds: float) -> None:
        pass

    client = TMDBClient(
        token=token,
        transport=httpx.MockTransport(fake_tmdb),
        sleep=fake_sleep,
    )

    try:
        with pytest.raises(TMDBError) as exc_info:
            await client.get_movie(603)
    finally:
        await client.aclose()

    assert token not in str(exc_info.value)
    assert token not in repr(exc_info.value)


@pytest.mark.asyncio
async def test_requests_have_explicit_timeouts():
    captured_timeouts = []

    def fake_tmdb(request: httpx.Request) -> httpx.Response:
        captured_timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json={"results": []})

    client = TMDBClient(
        token="secret-test-token",
        transport=httpx.MockTransport(fake_tmdb),
    )

    try:
        await client.search_movies("The Matrix")
    finally:
        await client.aclose()

    assert len(captured_timeouts) == 1
    assert captured_timeouts[0] == {
        "connect": 3.0,
        "read": 5.0,
        "write": 5.0,
        "pool": 5.0,
    }
