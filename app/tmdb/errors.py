class TMDBError(Exception):
    """Base exception for errors raised by our TMDB client."""


class TMDBNotFound(TMDBError):
    """The requested movie does not exist (HTTP 404)."""


class TMDBAuthError(TMDBError):
    """TMDB rejected the authentication credentials (HTTP 401)."""


class TMDBUnavailable(TMDBError):
    """TMDB is temporarily unavailable or a network request failed."""


class TMDBResponseError(TMDBError):
    """TMDB returned invalid or unexpected response data."""
