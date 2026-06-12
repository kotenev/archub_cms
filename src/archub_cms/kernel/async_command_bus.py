"""Async command bus: decouples command dispatch from execution by queuing
commands for background processing.

Complements the synchronous Mediator pattern for fire-and-forget operations
that don't need immediate results (e.g., reindex, bulk import, PDF generation).
"""

from __future__ import annotations

__all__ = ["AsyncCommandBus", "QueuedCommand"]

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueuedCommand:
    """A command waiting in the async bus queue."""

    command_id: str
    command_type: str
    payload: dict[str, Any]
    queued_at: float
    priority: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "payload": self.payload,
            "queued_at": self.queued_at,
            "priority": self.priority,
        }


class AsyncCommandBus:
    """In-memory async command bus with priority ordering."""

    def __init__(self) -> None:
        self._queue: list[QueuedCommand] = []
        self._completed: list[QueuedCommand] = []
        self._handlers: dict[str, Any] = {}

    def register_handler(self, command_type: str, handler: Any) -> None:
        self._handlers[command_type] = handler

    def enqueue(self, command_type: str, payload: dict[str, Any], *, priority: int = 0) -> str:
        from archub_cms.kernel.value_objects import Identity

        cmd_id = Identity.generate("cmd-").value
        self._queue.append(
            QueuedCommand(
                command_id=cmd_id,
                command_type=command_type,
                payload=payload,
                queued_at=time.time(),
                priority=priority,
            )
        )
        self._queue.sort(key=lambda c: c.priority, reverse=True)
        return cmd_id

    def dequeue(self, *, limit: int = 10) -> list[QueuedCommand]:
        batch = self._queue[:limit]
        self._queue = self._queue[limit:]
        return batch

    def process_one(self) -> dict[str, Any] | None:
        if not self._queue:
            return None
        cmd = self._queue.pop(0)
        handler = self._handlers.get(cmd.command_type)
        if handler is None:
            return {"command_id": cmd.command_id, "status": "no_handler"}
        try:
            result = handler(cmd.payload)
            self._completed.append(cmd)
            return {"command_id": cmd.command_id, "status": "completed", "result": result}
        except Exception as exc:
            return {"command_id": cmd.command_id, "status": "failed", "error": str(exc)}

    def process_batch(self, *, limit: int = 10) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for _ in range(min(limit, len(self._queue))):
            result = self.process_one()
            if result is not None:
                results.append(result)
        return results

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    def stats(self) -> dict[str, Any]:
        return {
            "pending": self.pending_count,
            "completed": self.completed_count,
            "handlers": list(self._handlers),
        }
