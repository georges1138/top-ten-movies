from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import Movie
from app.services.movies import (
    add_movie,
    delete_movie,
    get_movie,
    list_top_ten,
    update_rating_review,
)

pytestmark = pytest.mark.usefixtures("test_database_guard")


@pytest.mark.asyncio
async def test_get_movie_returns_none_when_not_found(db_session):
    result = await get_movie(db_session, -1)
    assert result is None


@pytest.mark.asyncio
async def test_get_movie_returns_existing_movie(db_session):
    movie = Movie(
        tmdb_id=999996,
        title="Service Test Movie",
        original_title="Service Test Movie",
    )

    db_session.add(movie)
    await db_session.flush()

    result = await get_movie(db_session, movie.id)

    assert result is not None
    assert result.id == movie.id
    assert result.title == "Service Test Movie"


@pytest.mark.asyncio
async def test_get_movie_with_fresh_session():
    settings = Settings()
    engine = make_engine(settings.database_url)

    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as write_session:
            async with write_session.begin():
                movie = Movie(
                    tmdb_id=999995,
                    title="Fresh Session Test",
                    original_title="Fresh Session Test",
                )
                write_session.add(movie)
                await write_session.flush()
                movie_id = movie.id
        async with session_factory() as read_session:
            result = await get_movie(read_session, movie_id)

            assert result is not None
            assert result.id == movie_id
            assert result.title == "Fresh Session Test"
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(Movie).where(Movie.tmdb_id == 999995))
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_add_movie_returns_created_movie(db_session):
    movie = await add_movie(
        db_session,
        tmdb_id=999994,
        title="Add Movie Test",
        original_title="Add Movie Test",
    )

    assert movie.id is not None
    assert movie.tmdb_id == 999994
    assert movie.title == "Add Movie Test"


@pytest.mark.asyncio
async def test_update_rating_review_changes_movie(db_session):
    movie = await add_movie(
        db_session,
        tmdb_id=999993,
        title="Rating Update Test",
        original_title="Rating Update Test",
    )

    updated = await update_rating_review(
        db_session,
        movie.id,
        rating=Decimal("9.0"),
        review="Fantastic movie!",
    )

    assert updated is not None
    assert updated.id == movie.id
    assert updated.rating == Decimal("9.0")
    assert updated.review == "Fantastic movie!"


@pytest.mark.asyncio
async def test_update_rating_review_returns_none_when_not_found(db_session):
    result = await update_rating_review(
        db_session,
        -1,
        rating=Decimal("9.0"),
        review="This movie does not exist",
    )

    assert result is None


@pytest.mark.asyncio
async def test_update_rating_review_rejects_invalid_rating(db_session):
    movie = await add_movie(
        db_session,
        tmdb_id=999992,
        title="Invalid Rating Update Test",
        original_title="Invalid Rating Update Test",
    )

    with pytest.raises(
        IntegrityError,
        match="ck_movies_rating_range",
    ):
        await update_rating_review(
            db_session,
            movie.id,
            rating=Decimal("11.0"),
            review="This rating should be rejected",
        )


@pytest.mark.asyncio
async def test_delete_movie_removes_existing_movie(db_session):
    movie = await add_movie(
        db_session,
        tmdb_id=999991,
        title="Delete Movie Test",
        original_title="Delete Movie Test",
    )

    deleted = await delete_movie(db_session, movie.id)

    assert deleted is True

    result = await get_movie(db_session, movie.id)
    assert result is None


@pytest.mark.asyncio
async def test_delete_movie_returns_false_when_not_found(db_session):
    deleted = await delete_movie(db_session, -1)

    assert deleted is False


@pytest.mark.asyncio
async def test_list_top_ten_orders_by_rating(db_session):
    low_rated = Movie(
        tmdb_id=999981,
        title="Low Rated Movie",
        original_title="Low Rated Movie",
        rating=Decimal("4.0"),
    )
    high_rated = Movie(
        tmdb_id=999982,
        title="High Rated Movie",
        original_title="High Rated Movie",
        rating=Decimal("10.0"),
    )
    medium_rated = Movie(
        tmdb_id=999983,
        title="Medium Rated Movie",
        original_title="Medium Rated Movie",
        rating=Decimal("7.0"),
    )

    db_session.add_all([low_rated, high_rated, medium_rated])
    await db_session.flush()

    movies = await list_top_ten(db_session)
    ratings = [movie.rating for movie in movies]

    assert ratings == [
        Decimal("10.0"),
        Decimal("7.0"),
        Decimal("4.0"),
    ]


@pytest.mark.asyncio
async def test_list_top_ten_breaks_rating_ties_by_creation_time(db_session):
    newer_time = datetime(2026, 2, 1, tzinfo=timezone.utc)
    older_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    newer_movie = Movie(
        tmdb_id=999984,
        title="Newer Movie",
        original_title="Newer Movie",
        rating=Decimal("9.0"),
        created_at=newer_time,
    )
    older_movie = Movie(
        tmdb_id=999985,
        title="Older Movie",
        original_title="Older Movie",
        rating=Decimal("9.0"),
        created_at=older_time,
    )

    db_session.add_all([newer_movie, older_movie])
    await db_session.flush()

    movies = await list_top_ten(db_session)
    titles = [movie.title for movie in movies]

    assert titles == ["Older Movie", "Newer Movie"]


@pytest.mark.asyncio
async def test_list_top_ten_places_unrated_movies_last(db_session):
    unrated_movie = Movie(
        tmdb_id=999986,
        title="Unrated Movie",
        original_title="Unrated Movie",
        rating=None,
    )
    low_rated_movie = Movie(
        tmdb_id=999987,
        title="Low Rated Movie",
        original_title="Low Rated Movie",
        rating=Decimal("2.0"),
    )

    db_session.add_all([unrated_movie, low_rated_movie])
    await db_session.flush()

    movies = await list_top_ten(db_session)
    titles = [movie.title for movie in movies]

    assert titles == ["Low Rated Movie", "Unrated Movie"]


@pytest.mark.asyncio
async def test_list_top_ten_returns_at_most_ten_movies(db_session):
    for i in range(11):
        movie = Movie(
            tmdb_id=999900 + i,
            title=f"Limit Test Movie {i}",
            original_title=f"Limit Test Movie {i}",
            rating=Decimal("5.0"),
        )
        db_session.add(movie)

    await db_session.flush()

    movies = await list_top_ten(db_session)

    assert len(movies) == 10
