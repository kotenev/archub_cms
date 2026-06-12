"""Full-text search service over the FTS5 index, with federated fallback.

Keeps the FTS5 index in sync with published knowledge documents (rebuilds when
the document count changes, or on explicit ``reindex``), and serves BM25-ranked
results. If FTS5 is unavailable, transparently falls back to the federated
lexical+semantic :class:`SearchService`.
"""

from __future__ import annotations

__all__ = ["FtsSearchService", "get_archub_fts_search_service"]

from typing import Any

from archub_cms.application.knowledge import (
    ArcHubKnowledgeBaseService,
    get_archub_knowledge_base_service,
)
from archub_cms.application.search_service import SearchService
from archub_cms.domain.search.models import SearchQuery
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.fts_index import FtsIndex


class FtsSearchService:
    def __init__(
        self,
        *,
        knowledge: ArcHubKnowledgeBaseService | None = None,
        index: FtsIndex | None = None,
    ) -> None:
        self._knowledge = knowledge or get_archub_knowledge_base_service()
        self._index = index or FtsIndex(Database(self._knowledge._cms.db_path))

    @property
    def available(self) -> bool:
        return self._index.available

    def _index_docs(self) -> list[dict[str, Any]]:
        # Use the full KnowledgeDocument objects (they carry the body, which the
        # dict projection from documents() omits) so FTS indexes real content.
        return [
            {
                "route_path": doc.route_path,
                "title": doc.title,
                "body": doc.body,
                "tags": list(doc.tags),
            }
            for doc in self._knowledge._documents()
        ]

    def reindex(self) -> dict[str, Any]:
        count = self._index.rebuild(self._index_docs())
        return {"available": self.available, "indexed": count}

    def _ensure_index(self) -> None:
        if not self._index.available:
            return
        if self._index.count() != len(self._knowledge._documents()):
            self.reindex()

    def search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        if not self._index.available:
            results = SearchService(self._knowledge).search(SearchQuery(q=query, limit=limit))
            return {
                "engine": "fallback-federated",
                "query": query,
                "items": [item.as_dict() for item in results.items],
                "total": results.total,
            }
        self._ensure_index()
        hits = self._index.search(query, limit=limit)
        return {
            "engine": "fts5",
            "query": query,
            "items": [hit.as_dict() for hit in hits],
            "total": len(hits),
        }


def get_archub_fts_search_service(
    *, knowledge: ArcHubKnowledgeBaseService | None = None
) -> FtsSearchService:
    return FtsSearchService(knowledge=knowledge)
