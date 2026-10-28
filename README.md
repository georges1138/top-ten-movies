# top-ten-movies

> **Modernization in progress**
>
> This repository contains the original Top Ten Movies
> application built with Flask in 2022.
>
> The project is undergoing a security audit and
> modernization toward FastAPI, including asynchronous
> integration with The Movie Database (TMDB) API.
>
> The existing Flask application remains runnable while
> the modernization work progresses.

Site created with Python Flask, Bootstrap and SQLAlchemy

A sample personal "Top Ten Movie Site" that uses the following Python tools:  Flask, REST APIs, requests, wtforms.  
The code also uses the external site: themoviedb.org APIs to update the movie posters and descriptions.  Then uses the REST APIs to add, edit and delete the movie posts.

This site also uses sqlite / SQLAlchemy to store and maintain the movie list.

## Running the Legacy Flask Application

The original Flask application remains available during
modernization.

### Requirements

- Python 3.13
- uv
- A TMDB API v3 key

### Local Setup (Windows PowerShell)

Clone the repository and open a terminal in the project directory.


Create the project's virtual environment and install
dependencies using the lockfile:

```powershell
uv sync --locked
```

Configure the required environment variables:

```powershell
$env:TMDB_API_KEY = [System.Net.NetworkCredential]::new("", (Read-Host "Enter TMDB v3 API key" -AsSecureString)).Password

$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"

$env:FLASK_DEBUG = "0"
```

Start the application:

```powershell
uv run main.py
```

Open http://127.0.0.1:5000/ in your browser.

Press Ctrl+C in the terminal to stop the server.

### Configuration Notes

See `.env.example` for the required environment variables.

The legacy Flask application does not automatically load
`.env` files. Environment variables must be configured
before starting the application.

Do not commit API keys, Flask secrets, or local database files.

## New FastAPI app (in progress)

The FastAPI replacement is being developed alongside the original
Flask application. The legacy `main.py` remains available.

The new application requires:

- `SECRET_KEY`: An application secret containing at least 32 characters.
- `TMDB_READ_TOKEN`: A nonempty TMDB v4 API Read Access Token.

Create a local `.env` file using `.env.example` as a starting point.
Keep actual credentials out of Git.

### Local PostgreSQL setup

The FastAPI application uses PostgreSQL 18 with asynchronous SQLAlchemy. Docker Compose provides a local database server.

**Requirements:** Docker Desktop (with Docker Compose), Python 3.13, and `uv`.

1. Copy `.env.example` to `.env` and configure `SECRET_KEY`, `TMDB_READ_TOKEN`, `POSTGRES_PASSWORD`, and `DATABASE_URL`.

   Use a PostgreSQL connection URL in this format:

   `postgresql+psycopg://movie_user:<your-password>@localhost:5432/movies`

   The password in `DATABASE_URL` must match `POSTGRES_PASSWORD`. Keep `.env` out of Git.

2. Start PostgreSQL from the repository root:

   ```powershell
   docker compose up -d db
   ```

   On a fresh PostgreSQL volume, `docker/postgres/init-test-db.sql` creates the separate `movies_test` database.

3. Apply the Alembic migrations to the development database:

   ```powershell
   uv run alembic upgrade head
   ```

4. To run database tests, change `DATABASE_URL` in your local `.env` to point to `movies_test` instead of `movies`, then run:

   ```powershell
   uv run alembic upgrade head
   uv run pytest -q
   ```

   Database integration tests require the database name to be exactly `movies_test`. The test guard rejects other database names to protect development data.

5. Optionally check that the SQLAlchemy models match the database schema:

   ```powershell
   uv run alembic check
   ```

**Existing Docker volume:** Initialization scripts only execute when PostgreSQL initializes a new, empty data directory. If you already have a PostgreSQL volume without `movies_test`, create that database manually using:

```powershell
docker compose exec -T db psql -U movie_user -d movies -c "CREATE DATABASE movies_test OWNER movie_user;"
```

Run this manual creation command only if `movies_test` does not already exist. Do not delete your Docker volume to rerun initialization.

Install the locked dependencies:

```powershell
uv sync --locked
```

Start FastAPI:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check the health endpoint:

`http://127.0.0.1:8000/healthz`

Expected response:

```json
{"status": "ok"}
```

The FastAPI application currently provides a health check,
configuration validation, and a PostgreSQL-backed Movie data layer
using asynchronous SQLAlchemy and Alembic migrations.

The Movie service supports adding, retrieving, updating ratings
and reviews, deleting, and listing the top ten movies. HTTP movie
routes and full feature parity with the legacy Flask application
are planned for later milestones.

Run the automated checks:

```powershell
uv run pytest
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
```
