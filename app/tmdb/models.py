from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator


class _TMDBMovieFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    original_title: str
    release_date: date | None = None
    overview: str | None = None
    poster_path: str | None = None

    @field_validator("release_date", "overview", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class SearchResult(_TMDBMovieFields):
    """A movie returned by a TMDB search."""


class MovieDetails(_TMDBMovieFields):
    """Details returned for an individual TMDB movie."""
