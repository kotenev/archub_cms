"""The ``LocalizedVariant`` aggregate (a node's culture-specific content)."""

from __future__ import annotations

__all__ = ["LocalizedVariant"]

from dataclasses import dataclass, field
from typing import Any

from archub_cms.domain.content.value_objects import Culture


@dataclass(frozen=True)
class LocalizedVariant:
    """A culture-specific draft/published payload for a content node."""

    node_id: str
    culture: Culture
    status: str = "draft"
    draft: dict[str, Any] = field(default_factory=dict)
    published: dict[str, Any] = field(default_factory=dict)
    updated_at: float = 0.0
    published_at: float | None = None
    updated_by: str = ""

    @property
    def is_published(self) -> bool:
        return self.status == "published" and bool(self.published)

    def title(self) -> str:
        source = self.published or self.draft
        return str(source.get("title") or source.get("hero_title") or "")

    def as_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        data = {
            "node_id": self.node_id,
            "culture": self.culture.value,
            "status": self.status,
            "is_published": self.is_published,
            "title": self.title(),
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }
        if include_payload:
            data["draft"] = dict(self.draft)
            data["published"] = dict(self.published)
        return data
