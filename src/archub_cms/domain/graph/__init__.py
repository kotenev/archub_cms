"""Knowledge-graph bounded context: backlinks, metrics, and canvas (Obsidian-style).

Builds on the edges the knowledge context already extracts (``[[wikilinks]]`` and
``/cms`` links). The pure :class:`GraphAnalyzer` derives the **backlinks** index
(incoming links per document — Obsidian's signature feature), graph **metrics**
(hubs, authorities, orphans, broken links) and a **canvas** layout (positioned
nodes + edges) for visualization.
"""

from __future__ import annotations

from archub_cms.domain.graph.analyzer import GraphAnalyzer
from archub_cms.domain.graph.models import (
    Canvas,
    CanvasEdge,
    CanvasNode,
    GraphMetrics,
)

__all__ = [
    "Canvas",
    "CanvasEdge",
    "CanvasNode",
    "GraphAnalyzer",
    "GraphMetrics",
]
