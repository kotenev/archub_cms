"""Example scheduled job plugin demonstrating ScheduledJobExt."""

from __future__ import annotations

from typing import Any

from archub_cms.extensibility.extension_points import ScheduledJobExt


class HealthCheckJob:
    """A scheduled job that logs a health check message."""

    def setup(self, context: Any) -> None:
        context.register(HealthCheckScheduledJob())


class HealthCheckScheduledJob(ScheduledJobExt):
    job_name = "health-check"
    cron_expression = "*/5 * * * *"

    def execute(self, payload: dict[str, Any]) -> str:
        import time

        return f"health-ok at {time.time()}"
