"""Application service for the runtime / RAG-export context.

``RuntimeQueryService`` reads the snapshot, export status and corpus retrieval.
``RuntimeCommandService`` exports the runtime snapshot to disk and rebuilds RAG
indexes, emitting ``runtime.exported`` / ``runtime.index.rebuilt`` events.
"""

from __future__ import annotations

__all__ = [
    "RuntimeCommandService",
    "RuntimeQueryService",
    "get_archub_runtime_query_service",
]

from pathlib import Path
from typing import Any

from archub_cms.domain.runtime.repository import RuntimeRepository
from archub_cms.infrastructure.sqlite.runtime_repository import CmsRuntimeRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service
from archub_cms.settings import ArcHubSettings


class RuntimeQueryService:
    def __init__(
        self, repository: RuntimeRepository, *, settings: ArcHubSettings | None = None
    ) -> None:
        self._repo = repository
        self._settings = settings or ArcHubSettings.from_env()

    def snapshot(self) -> dict[str, Any]:
        return self._repo.snapshot().as_dict()

    def status(self, export_dir: str | Path | None = None) -> dict[str, Any]:
        target = export_dir if export_dir is not None else self._settings.runtime_export_dir
        return self._repo.export_status(target).as_dict()

    def search(self, corpus_key: str, query: str, *, limit: int = 6) -> dict[str, Any]:
        hits = self._repo.search_rag(corpus_key, query, limit=limit)
        return {
            "corpus_key": corpus_key,
            "query": query,
            "items": [h.as_dict() for h in hits],
            "total": len(hits),
        }


class RuntimeCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        settings: ArcHubSettings | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._settings = settings or ArcHubSettings.from_env()
        self._bus = event_bus or get_event_bus()

    def export(
        self, *, export_dir: str | Path | None = None, actor: str = "system"
    ) -> dict[str, Any]:
        target = export_dir if export_dir is not None else self._settings.runtime_export_dir
        manifest = self._cms.export_runtime_content(target, exported_by=actor)
        # Distinct from the legacy activity action "runtime.exported" emitted by
        # cms._record_activity, so subscribers see exactly one domain event.
        self._bus.publish(
            ArcHubDomainEvent(
                "runtime.export.completed",
                str(manifest.get("export_dir") or ""),
                actor,
                {"counts": manifest.get("counts") or {}},
            )
        )
        return manifest

    def rebuild_indexes(
        self,
        *,
        corpus_key: str | None = None,
        model: str | None = None,
        export_dir: str | Path | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        target = export_dir if export_dir is not None else self._settings.runtime_export_dir
        result = self._cms.rebuild_exported_rag_indexes(
            corpus_key=corpus_key, model=model, export_dir=target
        )
        self._bus.publish(
            ArcHubDomainEvent(
                "runtime.index.rebuilt",
                corpus_key or "all",
                actor,
                {"model": model or ""},
            )
        )
        return result


def get_archub_runtime_query_service(
    *, cms: ArcHubCMSService | None = None, repository: RuntimeRepository | None = None
) -> RuntimeQueryService:
    return RuntimeQueryService(repository or CmsRuntimeRepository(cms))
