from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.tmdb.client import TMDBClient

APP_DIR = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings if settings is not None else Settings()
        app.state.engine = make_engine(app.state.settings.database_url)
        app.state.session_factory = make_session_factory(app.state.engine)

        app.state.tmdb_client = TMDBClient(
            token=app.state.settings.tmdb_read_token.get_secret_value()
        )

        try:
            yield
        finally:
            try:
                await app.state.tmdb_client.aclose()
            finally:
                await app.state.engine.dispose()

    app = FastAPI(
        title="Top Ten Movies",
        lifespan=lifespan,
    )

    app.mount(
        "/static",
        StaticFiles(directory=APP_DIR / "static"),
        name="static",
    )

    app.state.templates = Jinja2Templates(
        directory=APP_DIR / "templates",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
