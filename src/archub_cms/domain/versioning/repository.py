"""Repository port for the versioning context."""

from __future__ import annotations

__all__ = ["VersioningRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.versioning.version import Version


@runtime_checkable
class VersioningRepository(Protocol):
    def history(self, node_id: str, *, limit: int = 20) -> list[Version]: ...

    def get(self, node_id: str, version_no: int) -> Version | None: ...
