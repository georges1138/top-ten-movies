from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.main import create_app
from tests.conftest import require_test_database


@pytest.mark.asyncio
async def test_make_engine_returns_async_engine():
    database_url = "postgresql+psycopg://test:test@localhost:5432/test_movies"
    engine = make_engine(database_url)

    try:
        assert isinstance(engine, AsyncEngine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_factory_creates_async_session():
    database_url = "postgresql+psycopg://test:test@localhost:5432/test_movies"
    engine = make_engine(database_url)

    try:
        session_factory = make_session_factory(engine)

        async with session_factory() as session:
            assert isinstance(session, AsyncSession)
    finally:
        await engine.dispose()


def test_lifespan_disposes_engine():
    database_url = "postgresql+psycopg://test:test@localhost:5432/test_movies"
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url=database_url,
        _env_file=None,
    )
    mock_engine = AsyncMock()

    with (
        patch("app.main.make_engine", return_value=mock_engine),
        patch("app.main.make_session_factory"),
    ):
        with TestClient(create_app(settings)) as client:
            assert client.get("/healthz").status_code == 200

        mock_engine.dispose.assert_awaited_once()


def test_database_guard_rejects_development_database():
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/movies",
        _env_file=None,
    )

    with patch("tests.conftest.Settings", return_value=settings):
        with pytest.raises(
            RuntimeError,
            match="Database integration tests require the movies_test database",
        ):
            require_test_database()
