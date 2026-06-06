"""Application service for the scheduler bounded context.

Manages scheduled jobs (CRUD) and executes due jobs when the maintenance
worker ticks. Plugin-defined ``ScheduledJobExt`` extensions are discovered
and merged with user-created jobs.
"""

from __future__ import annotations

__all__ = ["SchedulerService", "get_archub_scheduler_service"]

import time
from typing import Any

from archub_cms.domain.scheduler.job import ScheduledJob
from archub_cms.domain.scheduler.repository import ScheduledJobRepository
from archub_cms.extensibility.host import PluginHost, get_plugin_host
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus


class SchedulerService:
    def __init__(
        self,
        *,
        repository: ScheduledJobRepository | None = None,
        plugin_host: PluginHost | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = repository
        self._host = plugin_host or get_plugin_host()
        self._bus = event_bus or get_event_bus()

    def list_jobs(self) -> list[dict[str, Any]]:
        if self._repo is None:
            return self._plugin_jobs()
        stored = [job.as_dict() for job in self._repo.list_all()]
        return stored + self._plugin_jobs()

    def create_job(self, job: ScheduledJob) -> dict[str, Any]:
        guard = job.validate()
        if not guard.ok:
            raise ValueError(getattr(guard, "error", "invalid job"))
        if self._repo is not None:
            self._repo.upsert(job)
        self._bus.publish(
            ArcHubDomainEvent(
                "scheduler.job.created", job.job_id, job.created_by, {"action": job.action}
            )
        )
        return job.as_dict()

    def pause_job(self, job_id: str) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("no repository configured")
        job = self._repo.get(job_id)
        if job is None:
            raise LookupError(job_id)
        result = job.pause()
        if not result.ok:
            raise ValueError(getattr(result, "error", "cannot pause"))
        self._repo.upsert(job)
        return job.as_dict()

    def resume_job(self, job_id: str) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("no repository configured")
        job = self._repo.get(job_id)
        if job is None:
            raise LookupError(job_id)
        result = job.resume()
        if not result.ok:
            raise ValueError(getattr(result, "error", "cannot resume"))
        self._repo.upsert(job)
        return job.as_dict()

    def tick(self) -> dict[str, Any]:
        now = time.time()
        fired: list[str] = []
        failed: list[str] = []

        plugin_jobs = self._host.scheduled_job_extensions
        for name, ext in plugin_jobs.items():
            try:
                ext.execute({})
                fired.append(name)
            except Exception:
                failed.append(name)

        if self._repo is not None:
            for job in self._repo.list_active():
                if job.can_fire(now):
                    try:
                        result = f"plugin:{job.action}"
                        job.mark_fired(result, now=now)
                        fired.append(job.job_id)
                    except Exception:
                        job.mark_failed("execution error", now=now)
                        failed.append(job.job_id)
                    self._repo.upsert(job)

        return {"fired": fired, "failed": failed, "now": now}

    def _plugin_jobs(self) -> list[dict[str, Any]]:
        return [
            {
                "job_id": f"plugin:{name}",
                "name": ext.job_name,
                "action": "plugin",
                "cron_expression": ext.cron_expression,
                "status": "active",
                "source": "plugin",
            }
            for name, ext in self._host.scheduled_job_extensions.items()
        ]


def get_archub_scheduler_service(
    *,
    repository: ScheduledJobRepository | None = None,
    plugin_host: PluginHost | None = None,
) -> SchedulerService:
    return SchedulerService(repository=repository, plugin_host=plugin_host)
