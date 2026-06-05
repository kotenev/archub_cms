"""Application service for the search context (federated + faceted).

Composes the knowledge service: candidate documents (with metadata) come from
``documents()``; ranking comes from ``hybrid_search()`` (lexical+semantic+plugin);
facets are computed by the pure :class:`FacetBuilder`. Filters and pagination are
applied over the candidate set.
"""

from __future__ import annotations

__all__ = ["SearchService", "get_archub_search_service"]

from typing import Any

from archub_cms.application.knowledge import (
    ArcHubKnowledgeBaseService,
    KnowledgeQuery,
    get_archub_knowledge_base_service,
)
from archub_cms.domain.search.facets import FacetBuilder
from archub_cms.domain.search.models import (
    SearchQuery,
    SearchResultItem,
    SearchResults,
)

_FACET_FIELDS = ("content_type_alias", "space_key", "tags")


def _norm(route: str) -> str:
    return (route or "").rstrip("/") or "/cms"


class SearchService:
    def __init__(self, knowledge: ArcHubKnowledgeBaseService | None = None) -> None:
        self._knowledge = knowledge or get_archub_knowledge_base_service()

    def search(self, query: SearchQuery) -> SearchResults:
        documents = self._knowledge.documents(KnowledgeQuery(q=query.q, limit=500))["items"]
        hits = self._knowledge.hybrid_search(query.q, limit=200)
        score_by_route = {_norm(h.route_path): h.score for h in hits}
        snippet_by_route = {_norm(h.route_path): h.excerpt for h in hits}

        candidates = [
            doc
            for doc in documents
            if query.matches(
                content_type=str(doc.get("content_type_alias") or ""),
                space=str(doc.get("space_key") or ""),
                tags=tuple(doc.get("tags") or ()),
            )
        ]
        facets = FacetBuilder.build(candidates, fields=_FACET_FIELDS)

        ranked = sorted(
            candidates,
            key=lambda doc: (
                -score_by_route.get(_norm(doc.get("route_path", "")), 0.0),
                doc.get("route_path", ""),
            ),
        )
        total = len(ranked)
        page = ranked[query.offset : query.offset + query.limit]

        items = tuple(
            SearchResultItem(
                route_path=str(doc.get("route_path") or ""),
                title=str(doc.get("title") or ""),
                content_type_alias=str(doc.get("content_type_alias") or ""),
                space_key=str(doc.get("space_key") or ""),
                tags=tuple(doc.get("tags") or ()),
                score=score_by_route.get(_norm(doc.get("route_path", "")), 0.0),
                snippet=snippet_by_route.get(_norm(doc.get("route_path", "")), "")
                or str(doc.get("summary") or ""),
            )
            for doc in page
        )
        return SearchResults(items=items, total=total, facets=tuple(facets), query=query)

    def search_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = SearchQuery(
            q=str(payload.get("q") or ""),
            content_types=tuple(payload.get("content_types") or ()),
            spaces=tuple(payload.get("spaces") or ()),
            tags=tuple(payload.get("tags") or ()),
            limit=int(payload.get("limit") or 20),
            offset=int(payload.get("offset") or 0),
        )
        return self.search(query).as_dict()


def get_archub_search_service(
    knowledge: ArcHubKnowledgeBaseService | None = None,
) -> SearchService:
    return SearchService(knowledge)
