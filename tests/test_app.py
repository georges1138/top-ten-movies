from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_health_returns_200():
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_secret_rejected_at_startup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("TMDB_READ_TOKEN", "fake-test-token")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://test:test@localhost:5432/test_movies",
    )

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(create_app()):
            pass

    assert exc_info.value.errors()[0]["loc"] == ("secret_key",)


@pytest.mark.parametrize("invalid_secret", ["", "too-short"])
def test_invalid_secret_rejected_at_startup(monkeypatch, tmp_path, invalid_secret):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_KEY", invalid_secret)
    monkeypatch.setenv("TMDB_READ_TOKEN", "fake-test-token")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://test:test@localhost:5432/test_movies",
    )

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(create_app()):
            pass
    assert exc_info.value.errors()[0]["loc"] == ("secret_key",)


def test_settings_repr_hides_secrets():
    secret = "my-private-test-secret-" + "x" * 32
    token = "my-private-test-token"

    settings = Settings(
        secret_key=secret,
        tmdb_read_token=token,
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )

    representation = repr(settings)

    assert secret not in representation
    assert token not in representation
    assert "**********" in representation


@pytest.mark.parametrize(
    "invalid_token",
    [None, "", "   "],
    ids=["missing", "empty", "whitespace-only"],
)
def test_invalid_tmdb_token_rejected(monkeypatch, tmp_path, invalid_token):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://test:test@localhost:5432/test_movies",
    )

    if invalid_token is None:
        monkeypatch.delenv("TMDB_READ_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TMDB_READ_TOKEN", invalid_token)

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(create_app()):
            pass

    assert exc_info.value.errors()[0]["loc"] == ("tmdb_read_token",)


def test_tmdb_client_is_closed_once_on_shutdown():
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )

    with patch("app.main.TMDBClient") as mock_client_class:
        mock_tmdb_client = mock_client_class.return_value
        mock_tmdb_client.aclose = AsyncMock()

        app = create_app(settings)

        with TestClient(app) as client:
            assert app.state.tmdb_client is mock_tmdb_client
            assert client.get("/healthz").status_code == 200

        mock_client_class.assert_called_once_with(token="fake-test-token")
        mock_tmdb_client.aclose.assert_awaited_once()


def test_get_tmdb_client_returns_shared_instance():
    from unittest.mock import MagicMock

    from starlette.requests import Request

    from app.tmdb.dependencies import get_tmdb_client

    shared_client = MagicMock()
    app = MagicMock()
    app.state.tmdb_client = shared_client

    request = MagicMock(spec=Request)
    request.app = app

    result = get_tmdb_client(request)

    assert result is shared_client
