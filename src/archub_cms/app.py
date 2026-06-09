"""FastAPI composition helpers for ArcHub CMS."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from archub_cms.demo import seed_demo_content
from archub_cms.extensibility.host import get_plugin_host
from archub_cms.services.jobs import ArcHubBackgroundWorker, get_archub_maintenance_service
from archub_cms.settings import ArcHubSettings
from archub_cms.web.admin_routes import admin_router
from archub_cms.web.collaboration_routes import collaboration_router
from archub_cms.web.itsm_routes import itsm_router
from archub_cms.web.platform_routes import platform_router
from archub_cms.web.routes import router

__all__ = ["create_archub_app"]


def create_archub_app(*, seed_demo: bool = True) -> FastAPI:
    """Create a standalone ArcHub CMS FastAPI app."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings = ArcHubSettings.from_env()
        worker = None
        # Boot the plugin runtime first: discover, permission-check and load
        # enabled plugins, subscribing their event hooks to the in-process event
        # bus — so events from demo seeding below are observed by plugins.
        get_plugin_host(reload=True, settings=settings)
        if seed_demo:
            seed_demo_content()
        if settings.background_jobs_enabled:
            worker = ArcHubBackgroundWorker(
                get_archub_maintenance_service(settings=settings),
                interval_seconds=settings.background_job_interval_seconds,
            )
            await worker.start()
        try:
            yield
        finally:
            if worker is not None:
                await worker.stop()

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
    app.include_router(platform_router)
    app.include_router(collaboration_router)
    app.include_router(admin_router)
    app.include_router(itsm_router)
    return app
