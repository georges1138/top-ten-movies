from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import make_engine
from app.models import Movie


@pytest.mark.asyncio
async def test_rating_outside_range_is_rejected():
    settings = Settings()
    engine = make_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            with pytest.raises(IntegrityError, match="ck_movies_rating_range"):
                await connection.execute(
                    text(
                        "INSERT INTO movies (tmdb_id, title, original_title, rating) "
                        "VALUES (:tmdb_id, :title, :original_title, :rating)"
                    ),
                    {
                        "tmdb_id": 999997,
                        "title": "Invalid Rating Test",
                        "original_title": "Invalid Rating Test",
                        "rating": 11,
                    },
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_rating", [Decimal("0.9"), Decimal("10.1")])
async def test_decimal_rating_outside_range_is_rejected(invalid_rating):
    settings = Settings()
    engine = make_engine(settings.database_url)

    try:
        async with engine.begin() as connection:
            with pytest.raises(
                IntegrityError,
                match="ck_movies_rating_range",
            ):
                await connection.execute(
                    text(
                        "INSERT INTO movies (tmdb_id, title, original_title, rating) "
                        "VALUES (:tmdb_id, :title, :original_title, :rating)"
                    ),
                    {
                        "tmdb_id": 987654322,
                        "title": "Invalid Decimal Rating Test",
                        "original_title": "Invalid Decimal Rating Test",
                        "rating": invalid_rating,
                    },
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_tmdb_id_is_rejected():
    settings = Settings()
    engine = make_engine(settings.database_url)

    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    "INSERT INTO movies (tmdb_id, title, original_title) "
                    "VALUES (:tmdb_id, :title, :original_title)"
                ),
                {
                    "tmdb_id": 999998,
                    "title": "First Test",
                    "original_title": "First Test",
                },
            )
            with pytest.raises(IntegrityError, match="movies_tmdb_id_key"):
                await connection.execute(
                    text(
                        "INSERT INTO movies (tmdb_id, title, original_title) "
                        "VALUES (:tmdb_id, :title, :original_title)"
                    ),
                    {
                        "tmdb_id": 999998,
                        "title": "Duplicate Test",
                        "original_title": "Duplicate Test",
                    },
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_decimal_rating_round_trips_exactly():
    settings = Settings()
    engine = make_engine(settings.database_url)

    try:
        async with engine.begin() as connection:
            movie = Movie(
                tmdb_id=987654321,
                title="Decimal Rating Test",
                original_title="Decimal Rating Test",
                rating=Decimal("7.5"),
            )

            async with AsyncSession(bind=connection) as session:
                session.add(movie)
                await session.flush()
                await session.refresh(movie)

                assert movie.rating == Decimal("7.5")

            await connection.rollback()
    finally:
        await engine.dispose()
