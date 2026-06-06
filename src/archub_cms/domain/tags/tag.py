"""Tag and TagNode domain models."""

from __future__ import annotations

__all__ = ["Tag", "TagNode"]

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tag:
    """A flat tag / label that can be applied to content."""

    slug: str
    display_name: str
    parent_slug: str = ""
    aliases: tuple[str, ...] = ()
    usage_count: int = 0
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "parent_slug": self.parent_slug,
            "aliases": list(self.aliases),
            "usage_count": self.usage_count,
            "description": self.description,
        }


@dataclass(frozen=True)
class TagNode:
    """A tag positioned in a hierarchy tree."""

    tag: Tag
    children: tuple[TagNode, ...] = ()

    def flatten(self) -> list[Tag]:
        result = [self.tag]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def as_dict(self) -> dict[str, Any]:
        payload = self.tag.as_dict()
        payload["children"] = [child.as_dict() for child in self.children]
        return payload
