"""Runtime repository adapter mapping legacy runtime/RAG reads to read models."""

from __future__ import annotations

__all__ = ["CmsRuntimeRepository"]

from pathlib import Path

from archub_cms.domain.runtime.models import ExportStatus, RagHit, RuntimeSnapshot
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


def _excerpt(text: str, limit: int = 240) -> str:
    clean = " ".join(str(text or "").split())
    return clean[:limit]


class CmsRuntimeRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot.from_snapshot(self._cms.runtime_snapshot())

    def export_status(self, export_dir: str | Path | None = None) -> ExportStatus:
        return ExportStatus.from_result(self._cms.runtime_export_status(export_dir))

    def search_rag(self, corpus_key: str, query: str, *, limit: int = 6) -> list[RagHit]:
        hits: list[RagHit] = []
        for node in self._cms.search_published_rag_materials(
            corpus_key or None, query, limit=limit
        ):
            payload = node.published
            hits.append(
                RagHit(
                    route_path=node.route_path,
                    title=str(payload.get("title") or node.name),
                    corpus_key=str(payload.get("corpus_key") or ""),
                    excerpt=_excerpt(str(payload.get("body") or "")),
                )
            )
        return hits
