import asyncio
import sys

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import make_engine


def pytest_asyncio_loop_factories(config, item):
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}


def require_test_database():
    database_url = Settings().database_url
    database_name = make_url(database_url).database

    if database_name != "movies_test":
        raise RuntimeError(
            "Database integration tests require the movies_test database."
        )


@pytest.fixture
def test_database_guard():
    require_test_database()


@pytest_asyncio.fixture
async def db_session():
    require_test_database()

    engine = make_engine(Settings().database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("DELETE FROM movies"))

                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                ) as session:
                    yield session
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()
