import argparse
import asyncio
import csv
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import make_engine, make_session_factory
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


def validate_mapping(legacy_rows, mapping_rows):
    legacy_ids = {row["id"] for row in legacy_rows}
    mapping_ids = [int(row["legacy_id"]) for row in mapping_rows]
    tmdb_ids = [int(row["tmdb_id"]) for row in mapping_rows]

    if len(mapping_ids) != len(set(mapping_ids)):
        raise ValueError("Duplicate legacy_id found in CSV")

    if set(mapping_ids) != legacy_ids:
        raise ValueError("CSV mappings do not match SQLite movie IDs")

    if len(tmdb_ids) != len(set(tmdb_ids)):
        raise ValueError("Duplicate tmdb_id found in CSV")

    legacy_titles = {row["id"]: row["title"] for row in legacy_rows}

    for row in mapping_rows:
        legacy_id = int(row["legacy_id"])

        if row["original_title"] != legacy_titles[legacy_id]:
            raise ValueError(f"Original title mismatch for legacy ID {legacy_id}")

    return {int(row["legacy_id"]): row for row in mapping_rows}


def confirm_import_database(database_url: str, confirmation: str) -> str:
    database_name = validate_import_database(database_url)

    if confirmation != database_name:
        raise ValueError("Database confirmation does not match destination")

    return database_name


def load_prepared_movies(
    sqlite_path: Path,
    mapping_path: Path,
) -> tuple[
    list[sqlite3.Row],
    dict[int, dict[str, str]],
    list[dict[str, object]],
]:
    sqlite_uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"

    with closing(sqlite3.connect(sqlite_uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        legacy_rows = connection.execute(
            """
            SELECT id, title, year, description, rating, review, img_url
            FROM movie
            ORDER BY id
            """
        ).fetchall()

    with mapping_path.open(newline="", encoding="utf-8") as file:
        mapping_rows = list(csv.DictReader(file))

    mapping_by_id = validate_mapping(legacy_rows, mapping_rows)

    prepared_movies = [
        prepare_movie(movie, mapping_by_id[movie["id"]]) for movie in legacy_rows
    ]

    return legacy_rows, mapping_by_id, prepared_movies


async def run_import(
    sqlite_path: Path,
    mapping_path: Path,
    database_url: str,
) -> None:
    _, _, prepared_movies = load_prepared_movies(
        sqlite_path,
        mapping_path,
    )

    engine = make_engine(database_url)

    try:
        session_factory = make_session_factory(engine)
        await import_prepared_movies(session_factory, prepared_movies)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or import legacy SQLite movies into PostgreSQL"
    )
    parser.add_argument("sqlite_path", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the PostgreSQL import",
    )
    parser.add_argument(
        "--confirm-database",
        metavar="NAME",
        help="Confirm the destination PostgreSQL database name",
    )
    args = parser.parse_args()

    mapping_path = Path("data/legacy_tmdb_ids.csv")

    if args.execute:
        if not args.confirm_database:
            parser.error("--execute requires --confirm-database NAME")

        database_url = Settings().database_url

        try:
            confirm_import_database(database_url, args.confirm_database)
        except ValueError as exc:
            parser.error(str(exc))

        try:
            asyncio.run(
                run_import(
                    args.sqlite_path,
                    mapping_path,
                    database_url,
                ),
                loop_factory=(
                    asyncio.SelectorEventLoop if sys.platform == "win32" else None
                ),
            )
        except ValueError as exc:
            parser.error(str(exc))

        print("PostgreSQL import completed successfully.")
        return

    try:
        legacy_rows, mapping_by_id, prepared_movies = load_prepared_movies(
            args.sqlite_path,
            mapping_path,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print("Validation passed: original titles match SQLite.")
    print("Validation passed: every SQLite movie has exactly one mapping.")
    print(f"Ready to transform {len(legacy_rows)} SQLite records.")

    print("Matched movies:")

    for movie in legacy_rows:
        mapping = mapping_by_id[movie["id"]]

        print(
            f"  {movie['id']}: {movie['title']} "
            f"-> {mapping['title']} "
            f"(TMDB {mapping['tmdb_id']})"
        )

    print(f"Prepared {len(prepared_movies)} movie identities (preview only).")

    longest_overview = max(
        (len(record["overview"] or "") for record in prepared_movies),
        default=0,
    )

    print(f"Longest prepared overview: {longest_overview} characters")
    print("Dry run complete: no movies imported.")


if __name__ == "__main__":
    main()
