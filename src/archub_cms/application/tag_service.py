"""Application service for the tag taxonomy context.

Manages hierarchical tags / labels that can be shared across content types
and spaces (Confluence-style labels, Obsidian/Wiki.js-style tags).
"""

from __future__ import annotations

__all__ = ["TagService", "get_archub_tag_service"]

from typing import Any

from archub_cms.domain.tags.repository import TagRepository
from archub_cms.domain.tags.tag import Tag


class TagService:
    def __init__(self, *, repository: TagRepository | None = None) -> None:
        self._repo = repository

    def list_all(self) -> dict[str, Any]:
        if self._repo is None:
            return {"items": [], "total": 0}
        tags = self._repo.list_all()
        return {
            "items": [tag.as_dict() for tag in tags],
            "total": len(tags),
        }

    def tree(self) -> dict[str, Any]:
        if self._repo is None:
            return {"tree": []}
        nodes = self._repo.tree()
        return {"tree": [node.as_dict() for node in nodes]}

    def upsert(self, tag: Tag) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("no repository configured")
        result = self._repo.upsert(tag)
        return result.as_dict()

    def delete(self, slug: str) -> bool:
        if self._repo is None:
            return False
        return self._repo.delete(slug)

    def find_by_alias(self, alias: str) -> dict[str, Any] | None:
        if self._repo is None:
            return None
        tag = self._repo.find_by_alias(alias)
        return tag.as_dict() if tag else None


def get_archub_tag_service(*, repository: TagRepository | None = None) -> TagService:
    return TagService(repository=repository)
