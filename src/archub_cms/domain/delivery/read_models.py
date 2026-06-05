"""Immutable read models for the delivery context (sitemap/feed/tags)."""

from __future__ import annotations

__all__ = ["FeedItem", "PublishedDocument", "SitemapEntry", "TagBucket"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PublishedDocument:
    """A published node projected for syndication."""

    route_path: str
    title: str
    content_type_alias: str
    updated_at: float = 0.0
    tags: tuple[str, ...] = ()
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_path": self.route_path,
            "title": self.title,
            "content_type_alias": self.content_type_alias,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class SitemapEntry:
    loc: str
    lastmod: str
    priority: str = "0.6"

    def as_dict(self) -> dict[str, Any]:
        return {"loc": self.loc, "lastmod": self.lastmod, "priority": self.priority}


@dataclass(frozen=True)
class FeedItem:
    title: str
    description: str
    link: str
    guid: str
    published_at_iso: str = ""
    tags: tuple[str, ...] = ()
    content_type_alias: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "link": self.link,
            "guid": self.guid,
            "published_at_iso": self.published_at_iso,
            "tags": list(self.tags),
            "content_type_alias": self.content_type_alias,
        }


@dataclass(frozen=True)
class TagBucket:
    tag: str
    slug: str
    count: int
    content_types: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "slug": self.slug,
            "count": self.count,
            "content_types": dict(self.content_types),
        }
