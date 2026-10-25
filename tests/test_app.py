import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_health_returns_200():
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
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

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(create_app()):
            pass

    assert exc_info.value.errors()[0]["loc"] == ("secret_key",)


@pytest.mark.parametrize("invalid_secret", ["", "too-short"])
def test_invalid_secret_rejected_at_startup(monkeypatch, tmp_path, invalid_secret):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_KEY", invalid_secret)
    monkeypatch.setenv("TMDB_READ_TOKEN", "fake-test-token")

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

    if invalid_token is None:
        monkeypatch.delenv("TMDB_READ_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TMDB_READ_TOKEN", invalid_token)

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(create_app()):
            pass

    assert exc_info.value.errors()[0]["loc"] == ("tmdb_read_token",)
