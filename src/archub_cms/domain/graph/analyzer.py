"""Pure graph analysis: backlinks, metrics and canvas layout.

``GraphAnalyzer`` is framework- and storage-agnostic: it takes plain node and
edge tuples (so it is trivially unit-testable) and derives the backlinks index,
graph metrics and a deterministic canvas layout.
"""

from __future__ import annotations

__all__ = ["GraphAnalyzer"]

import math

from archub_cms.domain.graph.models import Canvas, CanvasEdge, CanvasNode, GraphMetrics


def _norm(route: str) -> str:
    return (route or "").rstrip("/") or "/cms"


class GraphAnalyzer:
    def __init__(
        self,
        nodes: list[tuple[str, str]],
        edges: list[tuple[str, str, bool]],
    ) -> None:
        # nodes: (route_path, title); edges: (source, target, unresolved)
        self._titles: dict[str, str] = {_norm(route): title for route, title in nodes}
        self._routes: list[str] = list(self._titles)
        self._edges: list[tuple[str, str, bool]] = [
            (_norm(s), _norm(t), bool(u)) for s, t, u in edges
        ]

    # -- indexes -----------------------------------------------------------

    def backlinks(self) -> dict[str, list[str]]:
        """Map each target route to the resolved sources linking to it."""
        index: dict[str, list[str]] = {route: [] for route in self._routes}
        for source, target, unresolved in self._edges:
            if unresolved:
                continue
            index.setdefault(target, [])
            if source not in index[target]:
                index[target].append(source)
        return {route: sorted(sources) for route, sources in index.items()}

    def backlinks_for(self, route: str) -> list[str]:
        return self.backlinks().get(_norm(route), [])

    def outgoing(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {route: [] for route in self._routes}
        for source, target, _ in self._edges:
            index.setdefault(source, [])
            if target not in index[source]:
                index[source].append(target)
        return index

    # -- metrics -----------------------------------------------------------

    def metrics(self, *, top: int = 5) -> GraphMetrics:
        outgoing = self.outgoing()
        backlinks = self.backlinks()
        out_counts = sorted(
            ((r, len(t)) for r, t in outgoing.items() if t),
            key=lambda kv: (-kv[1], kv[0]),
        )
        in_counts = sorted(
            ((r, len(s)) for r, s in backlinks.items() if s),
            key=lambda kv: (-kv[1], kv[0]),
        )
        orphans = [r for r in self._routes if not outgoing.get(r) and not backlinks.get(r)]
        broken = sum(1 for _, _, unresolved in self._edges if unresolved)
        return GraphMetrics(
            node_count=len(self._routes),
            edge_count=len(self._edges),
            orphan_count=len(orphans),
            broken_link_count=broken,
            hubs=tuple(out_counts[:top]),
            authorities=tuple(in_counts[:top]),
        )

    def orphans(self) -> list[str]:
        outgoing = self.outgoing()
        backlinks = self.backlinks()
        return [r for r in self._routes if not outgoing.get(r) and not backlinks.get(r)]

    # -- canvas ------------------------------------------------------------

    def canvas(self, *, radius: float = 100.0) -> Canvas:
        """Deterministic circular layout; node weight = backlink count."""
        backlinks = self.backlinks()
        count = max(1, len(self._routes))
        nodes = []
        for index, route in enumerate(self._routes):
            angle = 2 * math.pi * index / count
            nodes.append(
                CanvasNode(
                    route_path=route,
                    title=self._titles.get(route, route),
                    x=radius * math.cos(angle),
                    y=radius * math.sin(angle),
                    weight=len(backlinks.get(route, [])),
                )
            )
        edges = tuple(CanvasEdge(s, t, u) for s, t, u in self._edges)
        return Canvas(nodes=tuple(nodes), edges=edges)
