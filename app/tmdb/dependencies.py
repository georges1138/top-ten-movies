from fastapi import Request

from app.tmdb.client import TMDBClient


def get_tmdb_client(request: Request) -> TMDBClient:
    """Return the TMDB client managed by the application lifespan."""
    return request.app.state.tmdb_client
