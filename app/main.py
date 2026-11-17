from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest, token_urlsafe

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import authenticate_admin
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.tmdb.client import TMDBClient

APP_DIR = Path(__file__).resolve().parent


def get_csrf_token(request: Request) -> str:
    """Return the existing CSRF token or create a new one."""
    token = request.session.get("csrf_token")

    if token is None:
        token = token_urlsafe(32)
        request.session["csrf_token"] = token

    return token


def validate_csrf_token(request: Request, submitted_token: str) -> bool:
    """Check whether a submitted CSRF token matches the session token."""
    expected_token = request.session.get("csrf_token")

    if not isinstance(expected_token, str):
        return False

    if not submitted_token:
        return False

    return compare_digest(expected_token, submitted_token)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
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

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key.get_secret_value(),
        session_cookie="top_ten_movies_session",
        max_age=3600,
        same_site="lax",
        https_only=settings.session_https_only,
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

    @app.get("/admin")
    async def admin_dashboard(request: Request):
        if "user_id" not in request.session:
            return RedirectResponse(
                url="/login",
                status_code=303,
            )

        return {"message": "Welcome to the admin dashboard"}

    @app.get("/login")
    async def admin_login_page(request: Request) -> HTMLResponse:
        csrf_token = get_csrf_token(request)

        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"csrf_token": csrf_token},
        )

    @app.post("/login")
    async def admin_login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        csrf_token: str | None = Form(None),
    ):

        if not isinstance(csrf_token, str) or not validate_csrf_token(
            request, csrf_token
        ):
            raise HTTPException(
                status_code=403,
                detail="Invalid CSRF token",
            )

        async with request.app.state.session_factory() as session:
            user = await authenticate_admin(
                session,
                username=username,
                password=password,
            )

        if user is None:
            request.session.clear()
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
            )

        request.session.clear()
        request.session["user_id"] = user.id

        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    @app.post("/logout")
    async def admin_logout(request: Request):
        request.session.clear()
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    return app


app = create_app()
