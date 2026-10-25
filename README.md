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

The FastAPI application currently provides a health check and
configuration validation. Movie routes and database integration
are planned for later milestones.

Run the automated checks:

```powershell
uv run pytest
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
```
