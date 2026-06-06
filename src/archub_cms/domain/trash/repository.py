"""Repository port for the trash context."""

from __future__ import annotations

__all__ = ["TrashRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.trash.item import TrashedItem


@runtime_checkable
class TrashRepository(Protocol):
    def list_trashed(self, *, limit: int = 100) -> list[TrashedItem]: ...
