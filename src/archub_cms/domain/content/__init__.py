"""Content authoring bounded context: the content-tree aggregate root.

``ContentNode`` is the aggregate root of the CMS — every space, page and
knowledge document is a node in a hierarchical tree with draft/published state.
This package holds the rich domain model (aggregate + value objects + events)
and the repository *port*; the SQLite adapter lives in
``archub_cms.infrastructure.sqlite.content_repository``.
"""

from __future__ import annotations

from archub_cms.domain.content.events import (
    node_created,
    node_deleted,
    node_published,
    node_updated,
)
from archub_cms.domain.content.node import ContentNode, NodeStatus
from archub_cms.domain.content.repository import ContentRepository
from archub_cms.domain.content.value_objects import Culture, RoutePath, Slug

__all__ = [
    "ContentNode",
    "ContentRepository",
    "Culture",
    "NodeStatus",
    "RoutePath",
    "Slug",
    "node_created",
    "node_deleted",
    "node_published",
    "node_updated",
]
