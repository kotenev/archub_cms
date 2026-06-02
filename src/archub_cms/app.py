"""FastAPI composition helpers for ArcHub CMS."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from archub_cms.demo import seed_demo_content
from archub_cms.web.routes import router

__all__ = ["create_archub_app"]


def create_archub_app(*, seed_demo: bool = True) -> FastAPI:
    """Create a standalone ArcHub CMS FastAPI app."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if seed_demo:
            seed_demo_content()
        yield

    app = FastAPI(
        title="ArcHub CMS",
        description="Standalone headless CMS, content builder and backoffice.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(router)
    return app
