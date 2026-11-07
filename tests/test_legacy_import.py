import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.legacy_import import (
    confirm_import_database,
    convert_rating,
    extract_poster_path,
    import_prepared_movies,
    insert_prepared_movies,
    legacy_created_at,
    prepare_movie,
    require_empty_movies,
    reset_movie_id_sequence,
    run_import,
    validate_import_database,
)
from app.models import Movie

pytestmark = pytest.mark.usefixtures("test_database_guard")


def test_poster_path_removes_extra_slash():
    result = extract_poster_path("https://image.tmdb.org/t/p/w500//example.jpg")

    assert result == "/example.jpg"


def test_poster_path_rejects_unexpected_host():
    with pytest.raises(ValueError, match="Unexpected poster image URL"):
        extract_poster_path("https://example.com/t/p/w500/example.jpg")


def test_convert_rating_preserves_decimal_value():
    assert convert_rating(9.2) == Decimal("9.2")
    assert convert_rating(None) is None


def test_legacy_created_at_preserves_id_order():
    first = legacy_created_at(2)
    last = legacy_created_at(15)

    assert first == datetime(2022, 4, 20, 0, 0, 2, tzinfo=timezone.utc)
    assert last == datetime(2022, 4, 20, 0, 0, 15, tzinfo=timezone.utc)
    assert first < last


def test_prepare_movie_preserves_original_values():
    description = "x" * 449
    review = "정말 좋아요!"

    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row

        connection.execute(
            """
            CREATE TABLE movie (
                id INTEGER,
                title TEXT,
                year TEXT,
                description TEXT,
                rating REAL,
                review TEXT,
                img_url TEXT
            )
            """
        )

        connection.execute(
            "INSERT INTO movie VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                7,
                "기생충",
                "2019",
                description,
                9.2,
                review,
                "https://image.tmdb.org/t/p/w500//poster.jpg",
            ),
        )

        movie = connection.execute("SELECT * FROM movie").fetchone()

        mapping = {
            "tmdb_id": "496243",
            "title": "Parasite",
        }

        result = prepare_movie(movie, mapping)

    assert result["id"] == 7
    assert result["tmdb_id"] == 496243
    assert result["title"] == "Parasite"
    assert result["original_title"] == "기생충"
    assert result["year"] == 2019
    assert result["overview"] == description
    assert result["review"] == review
    assert result["rating"] == Decimal("9.2")
    assert result["poster_path"] == "/poster.jpg"
    assert result["created_at"] == legacy_created_at(7)


@pytest.mark.asyncio
async def test_import_refuses_nonempty_movies_table(db_session):
    existing_movie = Movie(
        tmdb_id=999999,
        title="Existing Movie",
        original_title="Existing Movie",
    )

    db_session.add(existing_movie)
    await db_session.flush()

    with pytest.raises(ValueError, match="not empty"):
        await require_empty_movies(db_session)


@pytest.mark.asyncio
async def test_import_accepts_empty_movies_table(db_session):
    await require_empty_movies(db_session)


@pytest.mark.asyncio
async def test_insert_prepared_movies(db_session):
    record = {
        "id": 7,
        "tmdb_id": 496243,
        "title": "Parasite",
        "original_title": "기생충",
        "year": 2019,
        "overview": "A complete original description.",
        "review": "A social good time!",
        "rating": Decimal("9.8"),
        "poster_path": "/poster.jpg",
        "created_at": legacy_created_at(7),
    }

    await insert_prepared_movies(db_session, [record])

    movie = await db_session.get(Movie, 7)

    assert movie is not None
    assert movie.tmdb_id == 496243
    assert movie.title == "Parasite"
    assert movie.original_title == "기생충"
    assert movie.rating == Decimal("9.8")
    assert movie.overview == record["overview"]
    assert movie.review == record["review"]


@pytest.mark.asyncio
async def test_failed_import_rolls_back_all_movies(db_session):
    records = [
        {
            "id": 70,
            "tmdb_id": 900070,
            "title": "Valid Movie",
            "original_title": "Valid Movie",
            "rating": Decimal("9.2"),
        },
        {
            "id": 71,
            "tmdb_id": 900071,
            "title": "Invalid Movie",
            "original_title": "Invalid Movie",
            "rating": Decimal("11.0"),
        },
    ]

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await insert_prepared_movies(db_session, records)

    remaining_ids = (
        await db_session.scalars(select(Movie.id).where(Movie.id.in_([70, 71])))
    ).all()

    assert remaining_ids == []


@pytest.mark.asyncio
async def test_movies_id_has_attached_sequence(db_session):
    sequence_name = await db_session.scalar(
        text("SELECT pg_get_serial_sequence('movies', 'id')")
    )

    assert sequence_name is not None
    assert sequence_name.endswith("movies_id_seq")


@pytest.mark.asyncio
async def test_sequence_reset_uses_highest_movie_id():
    session = AsyncMock()

    await reset_movie_id_sequence(session)

    session.execute.assert_awaited_once()

    sql = str(session.execute.await_args.args[0])

    assert "pg_get_serial_sequence('movies', 'id')" in sql
    assert "(SELECT MAX(id) FROM movies)" in sql
    assert "true" in sql


@pytest.mark.asyncio
async def test_import_refuses_empty_batch(db_session):
    with pytest.raises(ValueError, match="no movies to import"):
        await insert_prepared_movies(db_session, [])


@pytest.mark.asyncio
async def test_sequence_reset_makes_next_id_16(db_session):
    await db_session.execute(
        text(
            """
            CREATE TEMP TABLE movies (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY
            ) ON COMMIT DROP
            """
        )
    )

    await db_session.execute(text("INSERT INTO movies (id) VALUES (2), (15)"))

    await reset_movie_id_sequence(db_session)

    next_id = await db_session.scalar(
        text("INSERT INTO movies DEFAULT VALUES RETURNING id")
    )

    assert next_id == 16


@pytest.mark.asyncio
async def test_failed_import_does_not_reset_sequence():
    session = AsyncMock()
    session.scalar.return_value = None
    session.begin = MagicMock(return_value=AsyncMock())

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = session

    with patch(
        "app.legacy_import.reset_movie_id_sequence",
        new_callable=AsyncMock,
    ) as reset_sequence:
        with pytest.raises(ValueError, match="no movies to import"):
            await import_prepared_movies(session_factory, [])

        reset_sequence.assert_not_awaited()


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_insert_failure():
    session = AsyncMock()
    transaction = AsyncMock()
    session.begin = MagicMock(return_value=transaction)

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = session

    records = [{"id": 1, "title": "Test Movie"}]

    with (
        patch(
            "app.legacy_import.insert_prepared_movies",
            new_callable=AsyncMock,
            side_effect=ValueError("Simulated insertion failure"),
        ),
        patch(
            "app.legacy_import.reset_movie_id_sequence",
            new_callable=AsyncMock,
        ) as reset_sequence,
    ):
        with pytest.raises(ValueError, match="Simulated insertion failure"):
            await import_prepared_movies(session_factory, records)

        reset_sequence.assert_not_awaited()

    assert transaction.__aexit__.await_count == 1
    assert transaction.__aexit__.await_args.args[0] is ValueError


@pytest.mark.asyncio
async def test_import_commit_visible_to_fresh_session():
    engine = make_engine(Settings().database_url)
    session_factory = make_session_factory(engine)

    record = {
        "id": 700001,
        "tmdb_id": 9700001,
        "title": "Transaction Test Movie",
        "original_title": "Transaction Test Movie",
        "rating": Decimal("9.2"),
    }

    imported = False

    try:
        with patch(
            "app.legacy_import.reset_movie_id_sequence",
            new_callable=AsyncMock,
        ) as reset_sequence:
            await import_prepared_movies(session_factory, [record])
            imported = True
            reset_sequence.assert_awaited_once()

        async with session_factory() as session:
            saved_movie = await session.get(Movie, 700001)

            assert saved_movie is not None
            assert saved_movie.tmdb_id == 9700001
            assert saved_movie.title == "Transaction Test Movie"
            assert saved_movie.rating == Decimal("9.2")

    finally:
        try:
            if imported:
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(
                            delete(Movie).where(
                                Movie.id == 700001,
                                Movie.tmdb_id == 9700001,
                            )
                        )
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_failed_import_leaves_no_committed_movies():
    engine = make_engine(Settings().database_url)
    session_factory = make_session_factory(engine)

    records = [
        {
            "id": 700002,
            "tmdb_id": 9700002,
            "title": "Valid Transaction Movie",
            "original_title": "Valid Transaction Movie",
            "rating": Decimal("9.0"),
        },
        {
            "id": 700003,
            "tmdb_id": 9700003,
            "title": "Invalid Transaction Movie",
            "original_title": "Invalid Transaction Movie",
            "rating": Decimal("11.0"),
        },
    ]

    try:
        with patch(
            "app.legacy_import.reset_movie_id_sequence",
            new_callable=AsyncMock,
        ) as reset_sequence:
            with pytest.raises(IntegrityError):
                await import_prepared_movies(session_factory, records)

            reset_sequence.assert_not_awaited()

        async with session_factory() as session:
            remaining_ids = (
                await session.scalars(
                    select(Movie.id).where(Movie.id.in_([700002, 700003]))
                )
            ).all()

            assert remaining_ids == []

    finally:
        try:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        delete(Movie).where(
                            Movie.id.in_([700002, 700003]),
                            Movie.tmdb_id.in_([9700002, 9700003]),
                        )
                    )
        finally:
            await engine.dispose()


def test_execute_flag_refuses_to_import():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.legacy_import",
            "instance/top-ten-movies.db",
            "--execute",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--execute requires --confirm-database NAME" in result.stderr


@pytest.mark.parametrize(
    ("database_url", "expected_name"),
    [
        ("postgresql+psycopg://user:password@localhost/movies", "movies"),
        ("postgresql+psycopg://user:password@localhost/movies_dev", "movies_dev"),
    ],
)
def test_validate_import_database_accepts_postgresql(database_url, expected_name):
    assert validate_import_database(database_url) == expected_name


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://user:password@localhost/movies_test",
        "sqlite:///movies.db",
        "postgresql+psycopg://user:password@localhost",
    ],
)
def test_validate_import_database_rejects_unsafe_targets(database_url):
    with pytest.raises(ValueError):
        validate_import_database(database_url)


def test_confirm_import_database_accepts_matching_name():
    database_url = "postgresql+psycopg://user:password@localhost/movies_dev"

    result = confirm_import_database(database_url, "movies_dev")

    assert result == "movies_dev"


@pytest.mark.parametrize(
    "confirmation",
    [
        "movies",
        "MOVIES_DEV",
        "",
    ],
)
def test_confirm_import_database_rejects_mismatch(confirmation):
    database_url = "postgresql+psycopg://user:password@localhost/movies_dev"

    with pytest.raises(
        ValueError,
        match="Database confirmation does not match destination",
    ):
        confirm_import_database(database_url, confirmation)


def test_cli_help_shows_database_confirmation():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.legacy_import",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--confirm-database NAME" in result.stdout
    assert "--execute" in result.stdout


def test_execute_with_confirmation_still_refuses_import():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.legacy_import",
            "instance/top-ten-movies.db",
            "--execute",
            "--confirm-database",
            "movies",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing import into test or unnamed database" in result.stderr


def test_execute_rejects_mismatched_database_confirmation():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.legacy_import",
            "instance/top-ten-movies.db",
            "--execute",
            "--confirm-database",
            "wrong_database",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing import into test or unnamed database" in result.stderr


def test_cli_rejects_confirmation_mismatch_with_allowed_target(monkeypatch, capsys):
    from app import legacy_import

    class FakeSettings:
        database_url = "postgresql+psycopg://user:password@localhost/movies_dev"

    monkeypatch.setattr(legacy_import, "Settings", FakeSettings)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "legacy_import.py",
            "instance/top-ten-movies.db",
            "--execute",
            "--confirm-database",
            "wrong_database",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        legacy_import.main()

    assert exc_info.value.code == 2
    assert "Database confirmation does not match destination" in capsys.readouterr().err


def test_cli_correct_confirmation_calls_run_import(monkeypatch, capsys):
    from app import legacy_import

    monkeypatch.setattr(legacy_import.sys, "platform", "win32")
    database_url = "postgresql+psycopg://user:password@localhost/movies_dev"

    class FakeSettings:
        database_url = "postgresql+psycopg://user:password@localhost/movies_dev"

    calls = []

    async def fake_run_import(sqlite_path, mapping_path, url):
        calls.append((sqlite_path, mapping_path, url))

    monkeypatch.setattr(legacy_import, "Settings", FakeSettings)
    monkeypatch.setattr(legacy_import, "run_import", fake_run_import)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "legacy_import.py",
            "instance/top-ten-movies.db",
            "--execute",
            "--confirm-database",
            "movies_dev",
        ],
    )

    with patch(
        "app.legacy_import.asyncio.run",
        wraps=legacy_import.asyncio.run,
    ) as run_spy:
        legacy_import.main()

    assert (
        run_spy.call_args.kwargs["loop_factory"]
        is legacy_import.asyncio.SelectorEventLoop
    )

    assert calls == [
        (
            Path("instance/top-ten-movies.db"),
            Path("data/legacy_tmdb_ids.csv"),
            database_url,
        )
    ]
    assert "PostgreSQL import completed successfully." in capsys.readouterr().out


def test_validate_mapping_rejects_missing_legacy_id():
    from app.legacy_import import validate_mapping

    legacy_rows = [
        {"id": 2, "title": "The Matrix"},
        {"id": 4, "title": "The Cannonball Run"},
    ]

    mapping_rows = [
        {
            "legacy_id": "2",
            "tmdb_id": "603",
            "original_title": "The Matrix",
            "title": "The Matrix",
        }
    ]

    with pytest.raises(
        ValueError,
        match="CSV mappings do not match SQLite movie IDs",
    ):
        validate_mapping(legacy_rows, mapping_rows)


def test_validate_mapping_rejects_extra_legacy_id():
    from app.legacy_import import validate_mapping

    legacy_rows = [
        {"id": 2, "title": "The Matrix"},
    ]

    mapping_rows = [
        {
            "legacy_id": "2",
            "tmdb_id": "603",
            "original_title": "The Matrix",
            "title": "The Matrix",
        },
        {
            "legacy_id": "999",
            "tmdb_id": "123456",
            "original_title": "Unknown Movie",
            "title": "Unknown Movie",
        },
    ]

    with pytest.raises(
        ValueError,
        match="CSV mappings do not match SQLite movie IDs",
    ):
        validate_mapping(legacy_rows, mapping_rows)


def test_validate_mapping_rejects_duplicate_legacy_id():
    from app.legacy_import import validate_mapping

    legacy_rows = [
        {"id": 2, "title": "The Matrix"},
    ]

    mapping_rows = [
        {
            "legacy_id": "2",
            "tmdb_id": "603",
            "original_title": "The Matrix",
            "title": "The Matrix",
        },
        {
            "legacy_id": "2",
            "tmdb_id": "11286",
            "original_title": "The Matrix",
            "title": "The Matrix",
        },
    ]

    with pytest.raises(
        ValueError,
        match="Duplicate legacy_id found in CSV",
    ):
        validate_mapping(legacy_rows, mapping_rows)


def test_validate_mapping_rejects_duplicate_tmdb_id():
    from app.legacy_import import validate_mapping

    legacy_rows = [
        {"id": 2, "title": "The Matrix"},
        {"id": 4, "title": "The Cannonball Run"},
    ]

    mapping_rows = [
        {
            "legacy_id": "2",
            "tmdb_id": "603",
            "original_title": "The Matrix",
            "title": "The Matrix",
        },
        {
            "legacy_id": "4",
            "tmdb_id": "603",
            "original_title": "The Cannonball Run",
            "title": "The Cannonball Run",
        },
    ]

    with pytest.raises(
        ValueError,
        match="Duplicate tmdb_id found in CSV",
    ):
        validate_mapping(legacy_rows, mapping_rows)


def test_validate_mapping_rejects_original_title_mismatch():
    from app.legacy_import import validate_mapping

    legacy_rows = [
        {"id": 7, "title": "기생충"},
    ]

    mapping_rows = [
        {
            "legacy_id": "7",
            "tmdb_id": "496243",
            "original_title": "The Matrix",
            "title": "Parasite",
        }
    ]

    with pytest.raises(
        ValueError,
        match="Original title mismatch for legacy ID 7",
    ):
        validate_mapping(legacy_rows, mapping_rows)


@pytest.fixture
def legacy_sqlite(tmp_path):
    path = tmp_path / "legacy.db"

    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            CREATE TABLE movie (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                year INTEGER,
                description TEXT,
                rating REAL,
                review TEXT,
                img_url TEXT
            )
            """
        )

        connection.execute(
            """
            INSERT INTO movie (
                id, title, year, description,
                rating, review, img_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "The Matrix",
                1999,
                "Test overview",
                9.2,
                "Test review",
                "https://image.tmdb.org/t/p/w500//abc.jpg",
            ),
        )

        connection.commit()

    return path


def test_cli_dry_run_calls_mapping_validation(monkeypatch, legacy_sqlite):
    from app import legacy_import

    def reject_mapping(legacy_rows, mapping_rows):
        assert len(legacy_rows) > 0
        assert len(mapping_rows) > 0
        raise RuntimeError("Mapping validation was called")

    monkeypatch.setattr(
        legacy_import,
        "validate_mapping",
        reject_mapping,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "legacy_import.py",
            str(legacy_sqlite),
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="Mapping validation was called",
    ):
        legacy_import.main()


@pytest.mark.asyncio
async def test_insert_prepared_movies_refuses_nonempty_table(db_session):
    existing_movie = Movie(
        tmdb_id=999999,
        title="Existing Movie",
        original_title="Existing Movie",
    )

    db_session.add(existing_movie)
    await db_session.flush()

    new_record = {
        "id": 70,
        "tmdb_id": 900070,
        "title": "New Movie",
        "original_title": "New Movie",
    }

    with pytest.raises(ValueError, match="not empty"):
        await insert_prepared_movies(db_session, [new_record])

    assert await db_session.get(Movie, 70) is None


def test_cli_reports_invalid_mapping_as_argument_error(
    monkeypatch,
    capsys,
    legacy_sqlite,
):
    from app import legacy_import

    def reject_mapping(legacy_rows, mapping_rows):
        raise ValueError("Duplicate tmdb_id found in CSV")

    monkeypatch.setattr(legacy_import, "validate_mapping", reject_mapping)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "legacy_import.py",
            str(legacy_sqlite),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        legacy_import.main()

    assert exc_info.value.code == 2

    captured = capsys.readouterr()
    assert "error: Duplicate tmdb_id found in CSV" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.asyncio
async def test_run_import_preserves_movie_data_and_refuses_second_import(
    legacy_sqlite,
    tmp_path,
):
    mapping_path = tmp_path / "mapping.csv"
    mapping_path.write_text(
        "legacy_id,tmdb_id,original_title,title\n2,603,The Matrix,The Matrix\n",
        encoding="utf-8",
    )

    database_url = Settings().database_url
    url = make_url(database_url)

    if url.drivername != "postgresql+psycopg" or url.database != "movies_test":
        raise RuntimeError(
            "End-to-end import test requires the PostgreSQL movies_test database"
        )

    engine = make_engine(database_url)
    session_factory = make_session_factory(engine)
    imported = False

    try:
        await run_import(legacy_sqlite, mapping_path, database_url)
        imported = True

        # Use a fresh session to prove the import was committed.
        async with session_factory() as session:
            movie = await session.get(Movie, 2)

            assert movie is not None
            assert movie.tmdb_id == 603
            assert movie.title == "The Matrix"
            assert movie.original_title == "The Matrix"
            assert movie.year == 1999
            assert movie.overview == "Test overview"
            assert movie.review == "Test review"
            assert movie.rating == Decimal("9.2")
            assert movie.poster_path == "/abc.jpg"
            assert movie.created_at == legacy_created_at(2)

        # Verify the next automatically generated ID follows the imported ID.
        async with session_factory() as session:
            async with session.begin():
                next_id = await session.scalar(
                    text("SELECT nextval(pg_get_serial_sequence('movies', 'id'))")
                )

                assert next_id == 3

        # A second import must not overwrite existing movies.
        with pytest.raises(ValueError, match="not empty"):
            await run_import(legacy_sqlite, mapping_path, database_url)

        async with session_factory() as session:
            movies = (await session.scalars(select(Movie))).all()
            assert len(movies) == 1
            assert movies[0].tmdb_id == 603

    finally:
        try:
            if imported:
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(
                            delete(Movie).where(
                                Movie.id == 2,
                                Movie.tmdb_id == 603,
                            )
                        )
        finally:
            await engine.dispose()
