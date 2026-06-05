"""Value objects / read models for the search context."""

from __future__ import annotations

__all__ = ["Facet", "SearchQuery", "SearchResultItem", "SearchResults"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchQuery:
    """A federated search request with optional facet filters + pagination."""

    q: str = ""
    content_types: tuple[str, ...] = ()
    spaces: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    limit: int = 20
    offset: int = 0

    def matches(self, *, content_type: str, space: str, tags: tuple[str, ...]) -> bool:
        if self.content_types and content_type not in self.content_types:
            return False
        if self.spaces and space not in self.spaces:
            return False
        if self.tags:
            doc_tags = {t.casefold() for t in tags}
            if not {t.casefold() for t in self.tags} <= doc_tags:
                return False
        return True


@dataclass(frozen=True)
class Facet:
    """A facet dimension and its value→count buckets (descending)."""

    field: str
    buckets: tuple[tuple[str, int], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "buckets": [{"value": value, "count": count} for value, count in self.buckets],
        }


@dataclass(frozen=True)
class SearchResultItem:
    route_path: str
    title: str
    content_type_alias: str = ""
    space_key: str = ""
    tags: tuple[str, ...] = ()
    score: float = 0.0
    snippet: str = ""
    source: str = "content"

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_path": self.route_path,
            "title": self.title,
            "content_type_alias": self.content_type_alias,
            "space_key": self.space_key,
            "tags": list(self.tags),
            "score": round(self.score, 4),
            "snippet": self.snippet,
            "source": self.source,
        }


@dataclass(frozen=True)
class SearchResults:
    items: tuple[SearchResultItem, ...] = ()
    total: int = 0
    facets: tuple[Facet, ...] = field(default_factory=tuple)
    query: SearchQuery = field(default_factory=SearchQuery)

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": [item.as_dict() for item in self.items],
            "total": self.total,
            "returned": len(self.items),
            "facets": [facet.as_dict() for facet in self.facets],
            "query": {
                "q": self.query.q,
                "content_types": list(self.query.content_types),
                "spaces": list(self.query.spaces),
                "tags": list(self.query.tags),
                "limit": self.query.limit,
                "offset": self.query.offset,
            },
        }
