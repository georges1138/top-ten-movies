import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Movie


async def require_empty_movies(session: AsyncSession) -> None:
    existing_id = await session.scalar(select(Movie.id).limit(1))

    if existing_id is not None:
        raise ValueError("Refusing import: movies table is not empty")


async def insert_prepared_movies(
    session: AsyncSession,
    prepared_movies: list[dict[str, object]],
) -> None:
    await require_empty_movies(session)
    if not prepared_movies:
        raise ValueError("Refusing import: no movies to import")
    for record in prepared_movies:
        session.add(Movie(**record))

    await session.flush()


async def reset_movie_id_sequence(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('movies', 'id'),
                (SELECT MAX(id) FROM movies),
                true
            )
            """
        )
    )


async def import_prepared_movies(
    session_factory,
    prepared_movies: list[dict[str, object]],
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await insert_prepared_movies(session, prepared_movies)
            await reset_movie_id_sequence(session)


def extract_poster_path(image_url: str | None) -> str | None:
    if not image_url:
        return None

    parsed = urlsplit(image_url)

    if parsed.scheme != "https" or parsed.netloc != "image.tmdb.org":
        raise ValueError("Unexpected poster image URL")

    prefix = "/t/p/w500/"

    if not parsed.path.startswith(prefix):
        raise ValueError("Unexpected TMDB poster URL format")

    filename = parsed.path[len(prefix) :].lstrip("/")

    if not filename:
        raise ValueError("Missing poster filename")

    return f"/{filename}"


def convert_rating(value: float | None) -> Decimal | None:
    if value is None:
        return None

    return Decimal(str(value))


def legacy_created_at(legacy_id: int) -> datetime:
    base_timestamp = datetime(2022, 4, 20, tzinfo=timezone.utc)
    return base_timestamp + timedelta(seconds=legacy_id)


def prepare_movie(
    movie: sqlite3.Row,
    mapping: dict[str, str],
) -> dict[str, object]:
    return {
        "id": movie["id"],
        "tmdb_id": int(mapping["tmdb_id"]),
        "title": mapping["title"],
        "original_title": movie["title"],
        "year": int(movie["year"]) if movie["year"] else None,
        "overview": movie["description"],
        "review": movie["review"],
        "rating": convert_rating(movie["rating"]),
        "poster_path": extract_poster_path(movie["img_url"]),
        "created_at": legacy_created_at(movie["id"]),
    }


def validate_import_database(database_url: str) -> str:
    url = make_url(database_url)

    if url.get_backend_name() != "postgresql":
        raise ValueError("Import requires PostgreSQL")

    database_name = url.database

    if not database_name or database_name == "movies_test":
        raise ValueError("Refusing import into test or unnamed database")

    return database_name


def confirm_import_database(database_url: str, confirmation: str) -> str:
    database_name = validate_import_database(database_url)

    if confirmation != database_name:
        raise ValueError("Database confirmation does not match destination")

    return database_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect legacy SQLite movies (import not yet implemented)"
    )
    parser.add_argument("sqlite_path", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the PostgreSQL import (not yet enabled)",
    )
    parser.add_argument(
        "--confirm-database",
        metavar="NAME",
        help="Confirm the destination PostgreSQL database name",
    )
    args = parser.parse_args()

    if args.execute:
        if not args.confirm_database:
            parser.error("--execute requires --confirm-database NAME")

        try:
            confirm_import_database(
                Settings().database_url,
                args.confirm_database,
            )
        except ValueError as exc:
            parser.error(str(exc))

        parser.error("PostgreSQL import execution is not yet enabled")

    sqlite_uri = f"{args.sqlite_path.resolve().as_uri()}?mode=ro"

    with closing(sqlite3.connect(sqlite_uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        count = connection.execute("SELECT COUNT(*) FROM movie").fetchone()[0]
        legacy_ids = [row[0] for row in connection.execute("SELECT id FROM movie")]
        legacy_titles = dict(connection.execute("SELECT id, title FROM movie"))
        legacy_rows = connection.execute(
            """
            SELECT id, title, year, description, rating, review, img_url
            FROM movie
            ORDER BY id
            """
        ).fetchall()

    mapping_path = Path("data/legacy_tmdb_ids.csv")

    with mapping_path.open(newline="", encoding="utf-8") as file:
        mapping_rows = list(csv.DictReader(file))
    mapping_ids = [int(row["legacy_id"]) for row in mapping_rows]

    tmdb_ids = [int(row["tmdb_id"]) for row in mapping_rows]

    if len(mapping_ids) != len(set(mapping_ids)):
        raise ValueError("Duplicate legacy_id found in CSV")

    if set(mapping_ids) != set(legacy_ids):
        raise ValueError("CSV mappings do not match SQLite movie IDs")

    if len(tmdb_ids) != len(set(tmdb_ids)):
        raise ValueError("Duplicate tmdb_id found in CSV")
    print("Validation passed: TMDB IDs are unique.")

    for row in mapping_rows:
        legacy_id = int(row["legacy_id"])

        if row["original_title"] != legacy_titles[legacy_id]:
            raise ValueError(f"Original title mismatch for legacy ID {legacy_id}")

    mapping_by_id = {int(row["legacy_id"]): row for row in mapping_rows}

    print("Validation passed: original titles match SQLite.")
    print("Validation passed: every SQLite movie has exactly one mapping.")
    print(f"Ready to transform {len(legacy_rows)} SQLite records.")

    first_movie = legacy_rows[0]
    print(
        f"First movie: ID={first_movie['id']}, "
        f"title={first_movie['title']}, "
        f"year={first_movie['year']}"
    )

    poster_path = extract_poster_path(first_movie["img_url"])
    print(f"First movie poster path: {poster_path}")

    raw_rating = first_movie["rating"]

    rating = Decimal(str(raw_rating)) if raw_rating is not None else None

    print(f"First movie rating: {rating}")
    print(f"Rating Python type: {type(rating).__name__}")

    print("Matched movies:")

    for movie in legacy_rows:
        mapping = mapping_by_id[movie["id"]]

        print(
            f"  {movie['id']}: {movie['title']} "
            f"-> {mapping['title']} "
            f"(TMDB {mapping['tmdb_id']})"
        )

    prepared_movies = []

    for movie in legacy_rows:
        mapping = mapping_by_id[movie["id"]]
        prepared_movies.append(prepare_movie(movie, mapping))

    print(f"Prepared {len(prepared_movies)} movie identities (preview only).")

    for record in prepared_movies:
        if record["id"] == 7:
            print(f"Parasite preview: {record}")

    longest_overview = max(len(record["overview"] or "") for record in prepared_movies)

    matrix = prepared_movies[0]

    print(f"Matrix prepared rating: {matrix['rating']}")
    print(f"Matrix rating type: {type(matrix['rating']).__name__}")
    print(f"Matrix prepared poster: {matrix['poster_path']}")
    print(f"First timestamp: {prepared_movies[0]['created_at'].isoformat()}")
    print(f"Last timestamp: {prepared_movies[-1]['created_at'].isoformat()}")
    print(f"Longest prepared overview: {longest_overview} characters")
    print(f"Found {count} legacy movies (read-only; nothing imported).")
    print(f"Loaded {len(mapping_rows)} verified TMDB mappings.")


if __name__ == "__main__":
    main()
