"""Platform admin dashboard — a single pane of glass over /api/platform/*.

A server-rendered HTML console (Confluence/Wiki.js-style) summarizing the
platform: bounded contexts, architectural patterns, the live plugin runtime, and
content-health. Read-only; it composes the capabilities facade, the plugin host
report and the analytics health into one page.
"""

from __future__ import annotations

__all__ = ["admin_router"]

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from archub_cms.application.analytics_service import get_archub_analytics_service
from archub_cms.application.platform import ArcHubPlatform
from archub_cms.extensibility.host import get_plugin_host
from archub_cms.web._common import templates

admin_router = APIRouter(tags=["admin"])


@admin_router.get("/admin/platform", response_class=HTMLResponse)
def platform_admin_dashboard(request: Request) -> HTMLResponse:
    host = get_plugin_host()
    capabilities = ArcHubPlatform(plugin_host=host).capabilities()
    report = host.report()
    health = get_archub_analytics_service().health()
    return templates().TemplateResponse(
        request,
        "archub_platform_admin.html",
        {
            "title": "ArcHub Platform Admin",
            "capabilities": capabilities,
            "report": report,
            "health": health,
            "extension_points": capabilities["plugins"]["extension_points"],
        },
    )
