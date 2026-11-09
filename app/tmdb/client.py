import asyncio
from collections.abc import Awaitable, Callable

import httpx
from pydantic import ValidationError

from app.tmdb.errors import (
    TMDBAuthError,
    TMDBNotFound,
    TMDBResponseError,
    TMDBUnavailable,
)
from app.tmdb.models import MovieDetails, SearchResult


class TMDBClient:
    """Async HTTP client for The Movie Database API."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(
        self,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sleep = sleep

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(5.0, connect=3.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(
        self,
        path: str,
        params: dict[str, str],
    ) -> dict:
        retry_statuses = {429, 502, 503, 504}

        for attempt in range(3):
            try:
                response = await self._client.get(path, params=params)
            except httpx.TransportError:
                if attempt == 2:
                    raise TMDBUnavailable("TMDB request failed") from None
                await self._sleep(0.1 * (2**attempt))
                continue

            if response.status_code == 401:
                raise TMDBAuthError("TMDB authentication failed")

            if response.status_code == 404:
                raise TMDBNotFound("TMDB movie not found")

            if response.status_code in retry_statuses:
                if attempt == 2:
                    raise TMDBUnavailable("TMDB is unavailable")
                await self._sleep(0.1 * (2**attempt))
                continue

            if response.status_code >= 500:
                raise TMDBUnavailable("TMDB server error")

            if response.status_code >= 400:
                raise TMDBResponseError("TMDB request was rejected")

            try:
                data = response.json()
            except ValueError:
                raise TMDBResponseError("Invalid TMDB JSON") from None

            if not isinstance(data, dict):
                raise TMDBResponseError("Unexpected TMDB response structure")

            return data

        raise TMDBUnavailable("TMDB request failed")

    async def search_movies(self, query: str) -> list[SearchResult]:
        data = await self._get_json(
            "search/movie",
            {"query": query, "language": "en-US"},
        )

        results = data.get("results")
        if not isinstance(results, list):
            raise TMDBResponseError("Invalid TMDB search results")

        try:
            return [SearchResult.model_validate(movie) for movie in results]
        except ValidationError:
            raise TMDBResponseError("Invalid TMDB movie data") from None

    async def get_movie(self, movie_id: int) -> MovieDetails:
        data = await self._get_json(
            f"movie/{movie_id}",
            {"language": "en-US"},
        )

        try:
            return MovieDetails.model_validate(data)
        except ValidationError:
            raise TMDBResponseError("Invalid TMDB movie data") from None
