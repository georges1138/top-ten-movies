from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security import hash_password, verify_password

_DUMMY_PASSWORD_HASH = hash_password("dummy-password-never-used-for-login")


async def authenticate_admin(
    session: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    """Authenticate an administrator using username and password."""
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
