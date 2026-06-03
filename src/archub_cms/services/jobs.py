"""Operational jobs for scheduled CMS maintenance."""

from __future__ import annotations

__all__ = [
    "ArcHubBackgroundWorker",
    "ArcHubMaintenanceService",
    "get_archub_maintenance_service",
]

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from archub_cms.application.publishing import get_archub_publishing_service
from archub_cms.application.webhooks import get_archub_webhook_service
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service
from archub_cms.settings import ArcHubSettings

logger = logging.getLogger("archub_cms")


class ArcHubMaintenanceService:
    """Runs the scheduled work that a production CMS host normally wires up.

    This mirrors Umbraco-style hosted jobs: scheduled publishing, webhook
    dispatch, runtime snapshot freshness, and health visibility. It is a facade
    over existing CMS service capabilities, so hosts can invoke it from cron,
    Celery, APScheduler, FastAPI lifespan tasks, or a worker process.
    """

    def __init__(
        self,
        cms: ArcHubCMSService | None = None,
        settings: ArcHubSettings | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._settings = settings or ArcHubSettings.from_env()

    def run_once(self, *, actor: str = "system") -> dict[str, Any]:
        workflow_result = get_archub_publishing_service(self._cms).apply_due_workflows(actor=actor)
        runtime_status = self._cms.runtime_export_status()
        runtime_export = None
        if bool(runtime_status.get("needs_export")):
            runtime_export = self._cms.export_runtime_content(exported_by=actor)
        webhook_result = get_archub_webhook_service(self._cms).dispatch_pending(
            limit=self._settings.webhook_dispatch_limit,
            actor=actor,
        )
        health = self._cms.content_health_report()
        return {
            "workflow": workflow_result.report,
            "workflow_events": [event.as_dict() for event in workflow_result.events],
            "runtime_status": runtime_status,
            "runtime_export": workflow_result.runtime_export or runtime_export,
            "runtime_export_error": workflow_result.runtime_export_error,
            "webhooks": webhook_result.payload,
            "webhook_events": [event.as_dict() for event in webhook_result.events],
            "health": {
                "ok": health.get("ok"),
                "issue_count": health.get("issue_count"),
                "error_count": health.get("error_count"),
                "warning_count": health.get("warning_count"),
            },
        }


@dataclass
class ArcHubBackgroundWorker:
    """Small asyncio worker for hosts that want in-process maintenance jobs."""

    service: ArcHubMaintenanceService
    interval_seconds: int = 60
    actor: str = "system"
    _task: asyncio.Task[None] | None = None
    _stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop(), name="archub-cms-maintenance")

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            await self._task

    async def _run_loop(self) -> None:
        stop_event = self._stop_event
        if stop_event is None:
            return
        interval = max(5, int(self.interval_seconds))
        while not stop_event.is_set():
            try:
                self.service.run_once(actor=self.actor)
            except Exception:
                logger.warning("ArcHub maintenance job failed", exc_info=True)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue


def get_archub_maintenance_service(
    cms: ArcHubCMSService | None = None,
    settings: ArcHubSettings | None = None,
) -> ArcHubMaintenanceService:
    return ArcHubMaintenanceService(cms=cms, settings=settings)
