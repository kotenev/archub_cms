"""Application service for the knowledge-graph context.

Pulls the edge-extracted :class:`KnowledgeGraph` from the knowledge service and
runs the pure :class:`GraphAnalyzer` over it to serve backlinks, metrics, orphans
and a canvas layout.
"""

from __future__ import annotations

__all__ = ["GraphService", "get_archub_graph_service"]

from typing import Any

from archub_cms.application.knowledge import (
    ArcHubKnowledgeBaseService,
    get_archub_knowledge_base_service,
)
from archub_cms.domain.graph.analyzer import GraphAnalyzer


class GraphService:
    def __init__(self, knowledge: ArcHubKnowledgeBaseService | None = None) -> None:
        self._knowledge = knowledge or get_archub_knowledge_base_service()

    def _analyzer(self, *, space_key: str = "", limit: int = 200) -> GraphAnalyzer:
        view = self._knowledge.graph(space_key=space_key, limit=limit)
        nodes = [(doc.route_path, doc.title) for doc in view.documents]
        edges = [(edge.source, edge.target, edge.unresolved) for edge in view.edges]
        return GraphAnalyzer(nodes, edges)

    def overview(self, *, space_key: str = "", limit: int = 200) -> dict[str, Any]:
        analyzer = self._analyzer(space_key=space_key, limit=limit)
        metrics = analyzer.metrics()
        return {
            "space_key": space_key,
            "metrics": metrics.as_dict(),
            "orphans": analyzer.orphans(),
        }

    def backlinks(
        self, route_path: str, *, space_key: str = "", limit: int = 500
    ) -> dict[str, Any]:
        analyzer = self._analyzer(space_key=space_key, limit=limit)
        sources = analyzer.backlinks_for(route_path)
        return {
            "route_path": route_path.rstrip("/") or "/cms",
            "backlinks": sources,
            "total": len(sources),
        }

    def backlinks_index(self, *, space_key: str = "", limit: int = 500) -> dict[str, Any]:
        index = self._analyzer(space_key=space_key, limit=limit).backlinks()
        return {
            "items": {route: sources for route, sources in index.items() if sources},
            "total": sum(1 for sources in index.values() if sources),
        }

    def canvas(self, *, space_key: str = "", limit: int = 200) -> dict[str, Any]:
        return self._analyzer(space_key=space_key, limit=limit).canvas().as_dict()


def get_archub_graph_service(
    knowledge: ArcHubKnowledgeBaseService | None = None,
) -> GraphService:
    return GraphService(knowledge)
