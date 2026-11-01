from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Movie


async def get_movie(session: AsyncSession, movie_id: int) -> Movie | None:
    return await session.get(Movie, movie_id)


async def add_movie(
    session: AsyncSession,
    *,
    tmdb_id: int,
    title: str,
    original_title: str,
) -> Movie:
    movie = Movie(
        tmdb_id=tmdb_id,
        title=title,
        original_title=original_title,
    )
    session.add(movie)
    await session.flush()
    return movie


async def update_rating_review(
    session: AsyncSession,
    movie_id: int,
    *,
    rating: Decimal | None,
    review: str | None,
) -> Movie | None:
    movie = await get_movie(session, movie_id)

    if movie is None:
        return None

    movie.rating = rating
    movie.review = review
    await session.flush()
    return movie


async def delete_movie(
    session: AsyncSession,
    movie_id: int,
) -> bool:
    movie = await get_movie(session, movie_id)

    if movie is None:
        return False
    await session.delete(movie)
    await session.flush()
    return True


async def list_top_ten(session: AsyncSession) -> list[Movie]:
    statement = (
        select(Movie)
        .order_by(
            Movie.rating.desc().nulls_last(),
            Movie.created_at.asc(),
            Movie.id.asc(),
        )
        .limit(10)
    )

    result = await session.execute(statement)
    return list(result.scalars().all())
