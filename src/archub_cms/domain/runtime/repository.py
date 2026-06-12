"""Repository port for the runtime context."""

from __future__ import annotations

__all__ = ["RuntimeRepository"]

from pathlib import Path
from typing import Protocol, runtime_checkable

from archub_cms.domain.runtime.models import ExportStatus, RagHit, RuntimeSnapshot


@runtime_checkable
class RuntimeRepository(Protocol):
    def snapshot(self) -> RuntimeSnapshot: ...

    def export_status(self, export_dir: str | Path | None = None) -> ExportStatus: ...

    def search_rag(self, corpus_key: str, query: str, *, limit: int = 6) -> list[RagHit]: ...
