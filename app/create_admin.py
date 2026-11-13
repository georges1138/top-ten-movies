import asyncio
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import User
from app.security import hash_password


def prompt_for_credentials() -> tuple[str, str]:
    """Prompt an operator for an admin username and password."""
    username = input("Admin username: ").strip()
    password = getpass("Admin password: ")
    return username, password


def validate_credentials(username: str, password: str) -> None:
    """Reject empty usernames and passwords."""
    if not username.strip():
        raise ValueError("Admin username cannot be empty.")

    if not password:
        raise ValueError("Admin password cannot be empty.")


async def username_exists(session: AsyncSession, username: str) -> bool:
    """Return whether an admin account already uses this username."""
    result = await session.execute(select(User.id).where(User.username == username))
    return result.scalar_one_or_none() is not None


async def create_admin(session: AsyncSession, username: str, password: str) -> User:
    """Prepare a new admin account, rejecting duplicate usernames."""
    validate_credentials(username, password)

    if await username_exists(session, username):
        raise ValueError("Admin username already exists.")

    user = User(
        username=username,
        password_hash=hash_password(password),
    )
    session.add(user)
    return user


async def save_admin(
    username: str,
    password: str,
    database_url: str | None = None,
) -> None:
    """Create an administrator within a managed database transaction."""
    if database_url is None:
        database_url = Settings().database_url

    engine = make_engine(database_url)

    session_factory = make_session_factory(engine)

    try:
        try:
            async with session_factory() as session:
                async with session.begin():
                    await create_admin(session, username, password)

        except IntegrityError as exc:
            original = exc.orig
            if (
                getattr(original, "sqlstate", None) == "23505"
                and getattr(
                    getattr(original, "diag", None),
                    "constraint_name",
                    None,
                )
                == "users_username_key"
            ):
                raise ValueError("Admin username already exists.") from exc
            raise
    finally:
        await engine.dispose()


def main() -> None:
    """Run the interactive administrator-creation command."""
    username, password = prompt_for_credentials()

    try:
        asyncio.run(save_admin(username, password))
    except ValueError as exc:
        print(f"Admin creation refused: {exc}")
        raise SystemExit(1) from None

    print("Admin account created successfully.")


if __name__ == "__main__":
    main()
