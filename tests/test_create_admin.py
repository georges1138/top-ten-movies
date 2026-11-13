from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from app.config import Settings
from app.create_admin import create_admin, main, save_admin, validate_credentials
from app.db import make_engine, make_session_factory
from app.models import User
from app.security import verify_password


@pytest.mark.asyncio
async def test_create_admin_hashes_password(db_session):
    password = "example-test-password"

    user = await create_admin(
        db_session,
        username="test_admin",
        password=password,
    )

    assert user.username == "test_admin"
    assert user.password_hash != password
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(password, user.password_hash) is True


@pytest.mark.asyncio
async def test_create_admin_rejects_duplicate_username(db_session):
    username = "duplicate_admin"

    await create_admin(
        db_session,
        username=username,
        password="first-test-password",
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="Admin username already exists"):
        await create_admin(
            db_session,
            username=username,
            password="second-test-password",
        )


@pytest.mark.parametrize(
    ("username", "password", "expected_error"),
    [
        ("", "test-password", "Admin username cannot be empty"),
        ("   ", "test-password", "Admin username cannot be empty"),
        ("test_admin", "", "Admin password cannot be empty"),
    ],
)
def test_validate_credentials_rejects_empty_values(username, password, expected_error):
    with pytest.raises(ValueError, match=expected_error):
        validate_credentials(username, password)


@pytest.mark.asyncio
async def test_create_admin_persists_hashed_password(db_session):
    password = "example-test-password"

    await create_admin(
        db_session,
        username="stored_admin",
        password=password,
    )

    await db_session.flush()

    result = await db_session.execute(
        select(User).where(User.username == "stored_admin")
    )
    stored_user = result.scalar_one()

    assert stored_user.username == "stored_admin"
    assert stored_user.password_hash != password
    assert stored_user.password_hash.startswith("$argon2id$")
    assert verify_password(password, stored_user.password_hash) is True


def test_admin_commit_uses_test_database():
    """Require the isolated test database before testing admin commits."""
    database_name = make_url(Settings().database_url).database

    assert database_name == "movies_test", "Admin commit tests must use movies_test"


@pytest.mark.asyncio
async def test_save_admin_commits_to_database():
    """Verify admin creation commits and cleans up the test account."""
    database_url = Settings().database_url
    assert make_url(database_url).database == "movies_test"

    username = f"test_admin_{uuid4().hex}"
    password = "example-test-password"

    engine = make_engine(database_url)

    try:
        await save_admin(username, password, database_url=database_url)

        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            stored_user = result.scalar_one()

            assert stored_user.password_hash != password
            assert verify_password(password, stored_user.password_hash)

    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(User).where(User.username == username))
        finally:
            await engine.dispose()


def test_admin_command_reports_failed_creation(capsys):
    """Do not report success when administrator creation fails."""
    with (
        patch(
            "app.create_admin.prompt_for_credentials",
            return_value=("test_admin", ""),
        ),
        patch(
            "app.create_admin.save_admin",
            new_callable=AsyncMock,
            side_effect=ValueError("Admin password cannot be empty."),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1

    output = capsys.readouterr().out
    assert "Admin creation refused: Admin password cannot be empty." in output
    assert "Admin account created successfully." not in output


@pytest.mark.asyncio
async def test_create_admin_rejects_empty_password_without_inserting(db_session):
    with pytest.raises(ValueError, match="Admin password cannot be empty"):
        await create_admin(
            db_session,
            username="invalid_admin",
            password="",
        )

    await db_session.flush()

    result = await db_session.execute(
        select(User).where(User.username == "invalid_admin")
    )

    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_save_admin_rolls_back_on_failure():
    """A failed transaction must not commit an administrator."""
    database_url = Settings().database_url
    assert make_url(database_url).database == "movies_test"

    username = f"rollback_admin_{uuid4().hex}"

    async def failing_create_admin(session, username, password):
        user = User(
            username=username,
            password_hash="temporary-test-hash",
        )
        session.add(user)
        await session.flush()
        raise RuntimeError("Simulated failure")

    with patch(
        "app.create_admin.create_admin",
        side_effect=failing_create_admin,
    ):
        with pytest.raises(RuntimeError, match="Simulated failure"):
            await save_admin(
                username,
                "example-test-password",
                database_url=database_url,
            )

    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            assert result.scalar_one_or_none() is None
    finally:
        await engine.dispose()
