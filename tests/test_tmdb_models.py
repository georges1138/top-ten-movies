from datetime import date

from app.tmdb.models import MovieDetails, SearchResult


def test_search_result_normalizes_empty_fields():
    movie = SearchResult.model_validate(
        {
            "id": 603,
            "title": "The Matrix",
            "original_title": "The Matrix",
            "release_date": "",
            "overview": "",
            "poster_path": None,
        }
    )

    assert movie.release_date is None
    assert movie.overview is None
    assert movie.poster_path is None


def test_movie_details_preserves_english_and_original_titles():
    movie = MovieDetails.model_validate(
        {
            "id": 496243,
            "title": "Parasite",
            "original_title": "기생충",
            "release_date": "2019-05-30",
            "overview": "A Korean thriller.",
            "poster_path": "/poster.jpg",
            "popularity": 100.5,
        }
    )

    assert movie.id == 496243
    assert movie.title == "Parasite"
    assert movie.original_title == "기생충"
    assert movie.release_date == date(2019, 5, 30)
    assert movie.overview == "A Korean thriller."
    assert movie.poster_path == "/poster.jpg"
    assert not hasattr(movie, "popularity")
