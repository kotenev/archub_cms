"""Value objects / read models for the knowledge-graph context."""

from __future__ import annotations

__all__ = ["Canvas", "CanvasEdge", "CanvasNode", "GraphMetrics"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphMetrics:
    """Aggregate metrics over the knowledge graph."""

    node_count: int
    edge_count: int
    orphan_count: int
    broken_link_count: int
    hubs: tuple[tuple[str, int], ...] = ()  # (route, outgoing_count)
    authorities: tuple[tuple[str, int], ...] = ()  # (route, backlink_count)

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "orphan_count": self.orphan_count,
            "broken_link_count": self.broken_link_count,
            "hubs": [{"route_path": r, "outgoing": c} for r, c in self.hubs],
            "authorities": [{"route_path": r, "backlinks": c} for r, c in self.authorities],
        }


@dataclass(frozen=True)
class CanvasNode:
    route_path: str
    title: str
    x: float
    y: float
    weight: int = 0  # backlink count → node size

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_path": self.route_path,
            "title": self.title,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "weight": self.weight,
        }


@dataclass(frozen=True)
class CanvasEdge:
    source: str
    target: str
    unresolved: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "unresolved": self.unresolved}


@dataclass(frozen=True)
class Canvas:
    nodes: tuple[CanvasNode, ...] = ()
    edges: tuple[CanvasEdge, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.as_dict() for n in self.nodes],
            "edges": [e.as_dict() for e in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }
