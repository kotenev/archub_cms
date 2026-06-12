"""Repository port for the edit-locks context."""

from __future__ import annotations

__all__ = ["LockRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.locks.lock import EditLock


@runtime_checkable
class LockRepository(Protocol):
    def get(self, node_id: str) -> EditLock | None: ...

    def list_active(self, *, limit: int = 100) -> list[EditLock]: ...
