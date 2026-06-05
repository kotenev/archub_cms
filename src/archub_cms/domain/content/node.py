"""The ``ContentNode`` aggregate root and its invariants."""

from __future__ import annotations

__all__ = ["ContentNode", "NodeStatus"]

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from archub_cms.domain.content.value_objects import PUBLIC_ROOT, RoutePath, Slug
from archub_cms.kernel.result import Err, Ok, Result

ROOT_NODE_ID = "root"


class NodeStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    TRASHED = "trashed"


@dataclass
class ContentNode:
    """Aggregate root for a node in the content tree.

    Mutating helpers enforce domain invariants (a node must have a name; only a
    node with a publishable draft may be published) and return a typed
    :class:`Result` rather than raising, so callers branch explicitly.
    """

    node_id: str
    parent_id: str | None
    content_type_alias: str
    name: str
    slug: Slug
    route_path: RoutePath
    level: int
    status: NodeStatus
    draft: dict[str, Any] = field(default_factory=dict)
    published: dict[str, Any] = field(default_factory=dict)
    sort_order: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    published_at: float | None = None
    created_by: str = ""
    updated_by: str = ""

    @property
    def is_root(self) -> bool:
        return self.node_id == ROOT_NODE_ID

    @property
    def is_published(self) -> bool:
        return self.status is NodeStatus.PUBLISHED and bool(self.published)

    @property
    def space_key(self) -> str:
        return self.route_path.space_segment

    def can_publish(self) -> Result[bool, str]:
        if not self.name.strip():
            return Err("node name is required")
        if not self.draft:
            return Err("cannot publish a node without a draft payload")
        title = str(self.draft.get("title") or self.draft.get("hero_title") or self.name).strip()
        if not title:
            return Err("a publishable node needs a title")
        return Ok(True)

    def title(self) -> str:
        source = self.published or self.draft
        return str(source.get("title") or source.get("hero_title") or self.name)

    def tags(self) -> tuple[str, ...]:
        source = self.published or self.draft
        raw = str(source.get("tags") or source.get("category") or "")
        seen: list[str] = []
        for token in raw.replace("#", ",").replace(" ", ",").split(","):
            clean = token.strip().casefold()
            if clean and clean not in seen:
                seen.append(clean)
        return tuple(seen)

    def as_dict(self, *, include_body: bool = False) -> dict[str, Any]:
        payload = {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "content_type_alias": self.content_type_alias,
            "name": self.name,
            "slug": self.slug.value,
            "route_path": self.route_path.value,
            "level": self.level,
            "status": self.status.value,
            "is_published": self.is_published,
            "space_key": self.space_key,
            "title": self.title(),
            "tags": list(self.tags()),
            "sort_order": self.sort_order,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }
        if include_body:
            payload["published"] = dict(self.published)
            payload["draft"] = dict(self.draft)
        return payload

    @classmethod
    def new_root(cls) -> ContentNode:
        return cls(
            node_id=ROOT_NODE_ID,
            parent_id=None,
            content_type_alias="root",
            name="Root",
            slug=Slug.root(),
            route_path=RoutePath(PUBLIC_ROOT),
            level=0,
            status=NodeStatus.DRAFT,
        )
