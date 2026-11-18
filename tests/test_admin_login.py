import base64
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner

from app.config import Settings
from app.db import get_session
from app.main import create_app, require_admin, require_csrf
from app.models import User


def extract_csrf_token(html: str) -> str:
    """Extract the CSRF token from the login form HTML."""
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        html,
    )
    assert match is not None, "CSRF token input not found"
    return match.group(1)


def make_admin_session_cookie(user_id: int) -> str:
    """Create a signed session cookie for a test administrator."""
    session_data = {"user_id": user_id}
    encoded_session = base64.b64encode(json.dumps(session_data).encode("utf-8"))
    signer = TimestampSigner("a" * 32)
    return signer.sign(encoded_session).decode("utf-8")


@pytest.fixture
def admin_test_app(db_session):
    """Create a test app whose DB dependency uses the isolated test session."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )
    app = create_app(settings)
    app.state.session_factory = lambda: db_session

    test_router = APIRouter()

    @test_router.get("/_test/admin-only")
    async def admin_only(user: User = Depends(require_admin)):
        return {"user_id": user.id}

    # Protected POSTs check admin access before CSRF:
    # anonymous users get a 303 redirect; authenticated users
    # with missing or invalid CSRF tokens get 403.
    @test_router.post(
        "/_test/admin-write",
        dependencies=[Depends(require_admin), Depends(require_csrf)],
    )
    async def admin_write():
        return {"message": "Admin write allowed"}

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.include_router(test_router)

    yield app

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_write_redirects_anonymous_user(admin_test_app):
    """Anonymous POST requests redirect before CSRF validation."""
    transport = ASGITransport(app=admin_test_app)

    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            "/_test/admin-write",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_admin_write_without_csrf_returns_403(
    admin_test_app,
    db_session,
):
    """An authenticated POST without CSRF must be rejected."""
    user = User(
        username="admin_write_no_csrf",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None
    signed_cookie = make_admin_session_cookie(user.id)

    transport = ASGITransport(app=admin_test_app)
    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            "/_test/admin-write",
            headers={"cookie": f"top_ten_movies_session={signed_cookie}"},
            follow_redirects=False,
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_write_with_valid_csrf_returns_200(
    admin_test_app,
    db_session,
):
    """An authenticated POST with a valid CSRF token succeeds."""
    user = User(
        username="admin_write_valid_csrf",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None

    csrf_token = "valid-test-csrf-token"
    session_data = {
        "user_id": user.id,
        "csrf_token": csrf_token,
    }
    encoded_session = base64.b64encode(json.dumps(session_data).encode("utf-8"))
    signed_cookie = TimestampSigner("a" * 32).sign(encoded_session).decode("utf-8")

    transport = ASGITransport(app=admin_test_app)
    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            "/_test/admin-write",
            headers={"cookie": f"top_ten_movies_session={signed_cookie}"},
            data={"csrf_token": csrf_token},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Admin write allowed"}


def test_login_get_without_csrf_returns_200():
    """The login page must be accessible without a CSRF submission."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
    )
    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text


@pytest.mark.asyncio
async def test_admin_only_redirects_anonymous_user(admin_test_app):
    """An anonymous GET to a protected route redirects to login."""
    transport = ASGITransport(app=admin_test_app)

    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.get(
            "/_test/admin-only",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_require_admin_accepts_existing_user(admin_test_app, db_session):
    """An administrator present in the database must be authorized."""
    user = User(
        username="authorization_test_admin",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None

    signed_cookie = make_admin_session_cookie(user.id)

    transport = ASGITransport(app=admin_test_app)
    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        client.cookies.set("top_ten_movies_session", signed_cookie)
        response = await client.get("/admin", follow_redirects=False)

        test_route_response = await client.get(
            "/_test/admin-only",
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the admin dashboard"}
    assert test_route_response.status_code == 200
    assert test_route_response.json() == {"user_id": user.id}


@pytest.mark.asyncio
async def test_require_admin_rejects_deleted_user(admin_test_app, db_session):
    """A deleted administrator must lose access and have their session cleared."""

    user = User(
        username="deleted_authorization_test_admin",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    user_id = user.id
    await db_session.delete(user)
    await db_session.flush()

    assert await db_session.get(User, user_id) is None
    signed_cookie = make_admin_session_cookie(user_id)
    transport = ASGITransport(app=admin_test_app)

    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.get(
            "/admin",
            headers={"cookie": f"top_ten_movies_session={signed_cookie}"},
            follow_redirects=False,
        )
        test_route_response = await client.get(
            "/_test/admin-only",
            headers={"cookie": f"top_ten_movies_session={signed_cookie}"},
            follow_redirects=False,
        )

        assert "top_ten_movies_session=" in response.request.headers.get("cookie", "")
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        assert "top_ten_movies_session=null" in response.headers["set-cookie"]
        assert "expires=" in response.headers["set-cookie"].lower()
        assert test_route_response.status_code == 303
        assert test_route_response.headers["location"] == "/login"
        assert (
            "top_ten_movies_session=null" in test_route_response.headers["set-cookie"]
        )


def test_admin_login_returns_identical_errors_for_invalid_credentials():
    """Invalid credentials must return HTTP 401."""
    settings = Settings(
        secret_key="a" * 32,
        tmdb_read_token="fake-test-token",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_movies",
        _env_file=None,
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
        _env_file=None,
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
        _env_file=None,
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
        _env_file=None,
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
        _env_file=None,
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
        _env_file=None,
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
        _env_file=None,
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


@pytest.mark.asyncio
async def test_admin_dashboard_accepts_authenticated_user(
    admin_test_app,
    db_session,
):
    """A successful login grants access to the admin dashboard."""
    user = User(
        username="dashboard_login_admin",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None

    transport = ASGITransport(app=admin_test_app)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=user,
    ):
        async with AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            csrf_response = await client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)

            login_response = await client.post(
                "/login",
                data={
                    "username": "dashboard_login_admin",
                    "password": "correct-test-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

            dashboard_response = await client.get(
                "/admin",
                follow_redirects=False,
            )

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/admin"
    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {"message": "Welcome to the admin dashboard"}


@pytest.mark.asyncio
async def test_admin_logout_clears_session(
    admin_test_app,
    db_session,
):
    """Logging out must clear the authenticated session."""
    user = User(
        username="logout_test_admin",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None

    transport = ASGITransport(app=admin_test_app)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=user,
    ):
        async with AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            csrf_response = await client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)

            login_response = await client.post(
                "/login",
                data={
                    "username": "logout_test_admin",
                    "password": "correct-test-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )
            assert login_response.status_code == 303

            new_csrf_response = await client.get("/login")
            logout_csrf_token = extract_csrf_token(new_csrf_response.text)

            logout_response = await client.post(
                "/logout",
                data={"csrf_token": logout_csrf_token},
                follow_redirects=False,
            )

            assert logout_response.status_code == 303
            assert logout_response.headers["location"] == "/login"
            assert "top_ten_movies_session" not in client.cookies

            dashboard_response = await client.get(
                "/admin",
                follow_redirects=False,
            )

    assert dashboard_response.status_code == 303
    assert dashboard_response.headers["location"] == "/login"


@pytest.mark.parametrize(
    "invalid_csrf_token",
    [None, "deliberately-invalid-token"],
    ids=["missing-token", "wrong-token"],
)
@pytest.mark.asyncio
async def test_logout_invalid_csrf_preserves_authenticated_session(
    invalid_csrf_token: str | None,
    admin_test_app,
    db_session,
):
    """Invalid CSRF must return 403 without clearing an authenticated session."""
    user = User(
        username="invalid_logout_csrf_admin",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None

    transport = ASGITransport(app=admin_test_app)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=user,
    ):
        async with AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            csrf_response = await client.get("/login")
            csrf_token = extract_csrf_token(csrf_response.text)

            login_response = await client.post(
                "/login",
                data={
                    "username": "invalid_logout_csrf_admin",
                    "password": "correct-test-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

            assert login_response.status_code == 303

            logout_data = (
                {} if invalid_csrf_token is None else {"csrf_token": invalid_csrf_token}
            )

            response = await client.post(
                "/logout",
                data=logout_data,
                follow_redirects=False,
            )

            assert response.status_code == 403
            assert "top_ten_movies_session" in client.cookies

            dashboard_response = await client.get(
                "/admin",
                follow_redirects=False,
            )

    assert dashboard_response.status_code == 200


@pytest.mark.asyncio
async def test_logout_rejects_cross_session_csrf_token(
    admin_test_app,
    db_session,
):
    """A token from another session must not log out an authenticated user."""
    user = User(
        username="cross_session_csrf_admin",
        password_hash="unused-test-hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None

    transport = ASGITransport(app=admin_test_app)

    with patch(
        "app.main.authenticate_admin",
        new_callable=AsyncMock,
        return_value=user,
    ):
        async with (
            AsyncClient(
                transport=transport,
                base_url="https://testserver",
            ) as client_a,
            AsyncClient(
                transport=transport,
                base_url="https://testserver",
            ) as client_b,
        ):
            # Authenticate client B.
            login_page = await client_b.get("/login")
            login_token = extract_csrf_token(login_page.text)

            login_response = await client_b.post(
                "/login",
                data={
                    "username": "cross_session_csrf_admin",
                    "password": "correct-test-password",
                    "csrf_token": login_token,
                },
                follow_redirects=False,
            )

            assert login_response.status_code == 303

            # Obtain a token belonging to client A.
            other_page = await client_a.get("/login")
            other_token = extract_csrf_token(other_page.text)

            # Obtain client B's own post-login CSRF token.
            own_page = await client_b.get("/login")
            own_token = extract_csrf_token(own_page.text)

            assert other_token != own_token

            # Attempt to log out B using A's token.
            logout_response = await client_b.post(
                "/logout",
                data={"csrf_token": other_token},
                follow_redirects=False,
            )

            dashboard_response = await client_b.get(
                "/admin",
                follow_redirects=False,
            )

            assert logout_response.status_code == 403
            assert "top_ten_movies_session" in client_b.cookies
            assert dashboard_response.status_code == 200
