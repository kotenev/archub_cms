"""ScheduledJob aggregate: a cron-like or one-shot job with execution history."""

from __future__ import annotations

__all__ = ["JobStatus", "ScheduledJob", "ScheduledJobError"]

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from archub_cms.kernel.result import Err, Ok, Result


class JobStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ScheduledJobError(Exception):
    """Raised when a scheduled job cannot be created or transitioned."""


@dataclass
class ScheduledJob:
    """Aggregate root for a scheduled operation."""

    job_id: str
    name: str
    action: str
    cron_expression: str = ""
    next_run_at: float = 0.0
    status: JobStatus = JobStatus.ACTIVE
    payload: dict[str, Any] = field(default_factory=dict)
    last_run_at: float = 0.0
    last_result: str = ""
    run_count: int = 0
    failure_count: int = 0
    created_by: str = ""
    tags: tuple[str, ...] = ()

    def can_fire(self, now: float) -> bool:
        return self.status == JobStatus.ACTIVE and now >= self.next_run_at > 0

    def mark_fired(self, result: str, *, now: float = 0.0) -> None:
        import time

        self.last_run_at = now or time.time()
        self.last_result = result
        self.run_count += 1
        if not self.cron_expression:
            self.status = JobStatus.COMPLETED

    def mark_failed(self, error: str, *, now: float = 0.0) -> None:
        import time

        self.last_run_at = now or time.time()
        self.last_result = error
        self.failure_count += 1
        self.run_count += 1

    def pause(self) -> Result:
        if self.status != JobStatus.ACTIVE:
            return Err("only active jobs can be paused")
        self.status = JobStatus.PAUSED
        return Ok(self)

    def resume(self) -> Result:
        if self.status != JobStatus.PAUSED:
            return Err("only paused jobs can be resumed")
        self.status = JobStatus.ACTIVE
        return Ok(self)

    def validate(self) -> Result:
        if not self.job_id.strip():
            return Err("job_id is required")
        if not self.action.strip():
            return Err("action is required")
        return Ok(self)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "action": self.action,
            "cron_expression": self.cron_expression,
            "next_run_at": self.next_run_at,
            "status": self.status.value,
            "payload": dict(self.payload),
            "last_run_at": self.last_run_at,
            "last_result": self.last_result,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "created_by": self.created_by,
            "tags": list(self.tags),
        }
