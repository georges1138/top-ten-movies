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
