import base64
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.config import Settings
from app.main import create_app


def extract_csrf_token(html: str) -> str:
    """Extract the CSRF token from the login form HTML."""
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        html,
    )
    assert match is not None, "CSRF token input not found"
    return match.group(1)


def test_admin_login_returns_identical_errors_for_invalid_credentials():
    """Invalid credentials must return HTTP 401."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
    )

    app = create_app(settings)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with TestClient(app, base_url="https://testserver") as client:
            csrf_response = client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)
            response = client.post(
                "/login",
                data={
                    "username": "unknown_admin",
                    "password": "incorrect-password",
                    "csrf_token": csrf_token,
                },
            )

            csrf_response = client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)
            wrong_password_response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "incorrect-password",
                    "csrf_token": csrf_token,
                },
            )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}

    assert "top_ten_movies_session" not in response.cookies
    assert wrong_password_response.status_code == response.status_code
    assert wrong_password_response.json() == response.json()


def test_admin_login_redirects_on_success():
    """Valid credentials must create a session and redirect."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
        session_https_only=True,
    )

    app = create_app(settings)
    fake_user = SimpleNamespace(id=123)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        with TestClient(app, base_url="https://testserver") as client:
            csrf_response = client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)
            response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "correct-test-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert "top_ten_movies_session" in response.cookies

    session_cookie = response.cookies["top_ten_movies_session"]

    signer = TimestampSigner(settings.secret_key.get_secret_value())
    signed_data = signer.unsign(session_cookie, max_age=3600)

    session_data = json.loads(base64.b64decode(signed_data))

    assert session_data["user_id"] == 123

    set_cookie = response.headers["set-cookie"].lower()
    cookie_attributes = {attribute.strip() for attribute in set_cookie.split(";")[1:]}

    assert "secure" in cookie_attributes
    assert "httponly" in cookie_attributes
    assert "samesite=lax" in cookie_attributes


def test_successful_login_replaces_previous_session_csrf_token():
    """Successful login must discard the previous session's CSRF token."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
        session_https_only=True,
    )

    app = create_app(settings)
    fake_user = SimpleNamespace(id=123)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        with TestClient(app, base_url="https://testserver") as client:
            first_page = client.get("/login")
            first_token = extract_csrf_token(first_page.text)

            login_response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "correct-test-password",
                    "csrf_token": first_token,
                },
                follow_redirects=False,
            )

            assert login_response.status_code == 303

            second_page = client.get("/login")
            second_token = extract_csrf_token(second_page.text)

            assert second_token != first_token


def test_admin_login_get_returns_csrf_token():
    """The login GET endpoint must generate a CSRF token."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
    )

    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/login")
        second_response = client.get("/login")

    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert len(extract_csrf_token(response.text)) > 0
    assert "top_ten_movies_session" in response.cookies
    assert second_response.status_code == 200
    assert extract_csrf_token(response.text) == extract_csrf_token(second_response.text)


def test_admin_login_rejects_missing_csrf_token():
    """Login requests without a CSRF token must be rejected."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
    )

    app = create_app(settings)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
    ) as mock_auth:
        with TestClient(app, base_url="https://testserver") as client:
            response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "example-test-password",
                },
            )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid CSRF token"}
    mock_auth.assert_not_awaited()


def test_admin_login_rejects_invalid_csrf_token():
    """A submitted CSRF token must match the session token."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
    )

    app = create_app(settings)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
    ) as mock_auth:
        with TestClient(app, base_url="https://testserver") as client:
            response = client.get("/login")
            assert response.status_code == 200

            login_response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "example-test-password",
                    "csrf_token": "deliberately-invalid-token",
                },
            )

    assert login_response.status_code == 403
    assert login_response.json() == {"detail": "Invalid CSRF token"}
    mock_auth.assert_not_awaited()


def test_admin_login_rejects_cross_session_csrf_token():
    """A CSRF token from another session must be rejected."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        env_file=None,
    )

    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as client_a:
        response_a = client_a.get("/login")
        token_a = extract_csrf_token(response_a.text)

    with TestClient(app, base_url="https://testserver") as client_b:
        response_b = client_b.get("/login")
        token_b = extract_csrf_token(response_b.text)
        with patch(
            "app.main.authenticate_admin",
            new_callable=AsyncMock,
        ) as mock_auth:
            login_response = client_b.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "example-test-password",
                    "csrf_token": token_a,
                },
            )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert token_a != token_b
    assert login_response.status_code == 403
    assert login_response.json() == {"detail": "Invalid CSRF token"}
    mock_auth.assert_not_awaited()


def test_admin_dashboard_redirects_unauthenticated_user():
    """Visitors without a session must be redirected to login."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )

    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_dashboard_accepts_authenticated_user():
    """A successful login grants access to the admin dashboard."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )

    app = create_app(settings)
    fake_user = SimpleNamespace(id=123)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        with TestClient(app, base_url="https://testserver") as client:
            csrf_response = client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)

            login_response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "correct-test-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

            dashboard_response = client.get("/admin")

    assert login_response.status_code == 303
    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {"message": "Welcome to the admin dashboard"}


def test_admin_logout_clears_session():
    """Logging out must clear the authenticated session."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )

    app = create_app(settings)
    fake_user = SimpleNamespace(id=123)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        with TestClient(app, base_url="https://testserver") as client:
            csrf_response = client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)

            login_response = client.post(
                "/login",
                data={
                    "username": "test_admin",
                    "password": "correct-test-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

            assert login_response.status_code == 303

            logout_response = client.post(
                "/logout",
                follow_redirects=False,
            )

            dashboard_response = client.get(
                "/admin",
                follow_redirects=False,
            )

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"
    assert "top_ten_movies_session" not in client.cookies
    assert dashboard_response.status_code == 303
    assert dashboard_response.headers["location"] == "/login"
