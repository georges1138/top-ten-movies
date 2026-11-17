from unittest.mock import patch

import pytest

from app.auth import _DUMMY_PASSWORD_HASH, authenticate_admin
from app.create_admin import create_admin


@pytest.mark.asyncio
async def test_authenticate_admin_accepts_valid_credentials(db_session):
    """A valid username and password authenticate successfully."""
    username = "login_test_admin"
    password = "example-test-password"

    await create_admin(
        db_session,
        username=username,
        password=password,
    )
    await db_session.flush()

    authenticated_user = await authenticate_admin(
        db_session,
        username=username,
        password=password,
    )

    assert authenticated_user is not None
    assert authenticated_user.username == username


@pytest.mark.asyncio
async def test_authenticate_admin_rejects_wrong_password(db_session):
    """An incorrect password must not authenticate."""
    username = "wrong_password_admin"

    await create_admin(
        db_session,
        username=username,
        password="correct-test-password",
    )
    await db_session.flush()

    authenticated_user = await authenticate_admin(
        db_session,
        username=username,
        password="incorrect-test-password",
    )

    assert authenticated_user is None


@pytest.mark.asyncio
async def test_authenticate_admin_rejects_unknown_username(db_session):
    """A nonexistent username must not authenticate."""
    authenticated_user = await authenticate_admin(
        db_session,
        username="nonexistent_login_admin",
        password="example-test-password",
    )

    assert authenticated_user is None


@pytest.mark.asyncio
async def test_unknown_username_performs_dummy_password_verification(db_session):
    """Unknown usernames must still trigger password verification."""
    password = "example-test-password"

    with patch("app.auth.verify_password", return_value=False) as mock_verify:
        authenticated_user = await authenticate_admin(
            db_session,
            username="unknown_dummy_check_admin",
            password=password,
        )

    assert authenticated_user is None
    mock_verify.assert_called_once()

    assert mock_verify.call_args.args[0] == password
    assert mock_verify.call_args.args[1] == _DUMMY_PASSWORD_HASH
