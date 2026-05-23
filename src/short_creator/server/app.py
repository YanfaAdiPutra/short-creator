"""FastAPI application — mounts API routes and (optionally) the built frontend."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routes import crop, jobs, projects, recommend, render, settings, style, transcription


def _frontend_dir() -> Path | None:
    """Locate the built frontend bundle if it exists."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist",
        Path(__file__).resolve().parent / "static",
    ]
    for c in candidates:
        if c.exists() and (c / "index.html").exists():
            return c
    return None


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="short-creator",
        description="Turn long videos into 9:16 shorts.",
    )

    # CORS — allow the Vite dev server (5173) to talk to the API during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    api_routers = [
        projects.router,
        transcription.router,
        recommend.router,
        crop.router,
        style.router,
        render.router,
        jobs.router,
        settings.router,
    ]
    for router in api_routers:
        app.include_router(router, prefix="/api")

    front = _frontend_dir()
    if front is not None:
        assets = front / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(front / "index.html")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str) -> FileResponse:
            # API requests are already matched by routers above; this handles
            # SPA client-side routes like /projects/abc/crop.
            target = front / full_path
            if target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(front / "index.html")
    else:
        @app.get("/")
        def dev_root() -> RedirectResponse:
            return RedirectResponse(url="http://localhost:5173/")

    return app


app = create_app()
