"""Domain models for ArcHub knowledge-base bounded context."""

from __future__ import annotations

__all__ = [
    "KnowledgeDocument",
    "KnowledgeEdge",
    "KnowledgeGraph",
    "KnowledgeSpace",
    "KnowledgeSource",
    "KnowledgeAnswer",
    "extract_knowledge_links",
    "slug_to_space_key",
]

import re
from dataclasses import dataclass, field
from typing import Any

_WIKI_LINK_RE = re.compile(r"\[\[([^]|#]+)(?:#[^]|]+)?(?:\|[^]]+)?]]")
_MARKDOWN_LINK_RE = re.compile(r"\[[^]]+](/cms/[^)\s]+)\)")
_CMS_PATH_RE = re.compile(r"(?<![\w/])(/cms/[A-Za-z0-9_./-]+)")
_SPACE_KEY_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class KnowledgeSpace:
    """Corporate knowledge space similar to Confluence spaces or wiki roots."""

    key: str
    name: str
    root_node_id: str
    route_path: str
    document_count: int = 0
    updated_at: float = 0.0
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "root_node_id": self.root_node_id,
            "route_path": self.route_path,
            "document_count": self.document_count,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class KnowledgeDocument:
    """Published knowledge document projection."""

    node_id: str
    space_key: str
    title: str
    route_path: str
    content_type_alias: str
    summary: str = ""
    body: str = ""
    tags: tuple[str, ...] = ()
    source_path: str = ""
    updated_at: float = 0.0

    @property
    def markdown_path(self) -> str:
        clean = self.route_path.removeprefix("/cms/").strip("/") or "index"
        return f"{clean}.md"

    def as_dict(self, *, include_body: bool = False) -> dict[str, Any]:
        payload = {
            "node_id": self.node_id,
            "space_key": self.space_key,
            "title": self.title,
            "route_path": self.route_path,
            "content_type_alias": self.content_type_alias,
            "summary": self.summary,
            "tags": list(self.tags),
            "source_path": self.source_path,
            "updated_at": self.updated_at,
            "markdown_path": self.markdown_path,
        }
        if include_body:
            payload["body"] = self.body
        return payload


@dataclass(frozen=True)
class KnowledgeEdge:
    """Directed relation between two knowledge documents or a missing target."""

    source: str
    target: str
    relation: str = "links_to"
    unresolved: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "unresolved": self.unresolved,
        }


@dataclass(frozen=True)
class KnowledgeGraph:
    """Knowledge graph read model for backlinks, orphan detection, and audit."""

    documents: tuple[KnowledgeDocument, ...]
    edges: tuple[KnowledgeEdge, ...]
    orphaned_documents: tuple[KnowledgeDocument, ...] = ()
    unresolved_links: tuple[KnowledgeEdge, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "documents": [item.as_dict() for item in self.documents],
            "edges": [item.as_dict() for item in self.edges],
            "orphaned_documents": [item.as_dict() for item in self.orphaned_documents],
            "unresolved_links": [item.as_dict() for item in self.unresolved_links],
            "document_count": len(self.documents),
            "edge_count": len(self.edges),
            "orphaned_count": len(self.orphaned_documents),
            "unresolved_count": len(self.unresolved_links),
        }


@dataclass(frozen=True)
class KnowledgeSource:
    """Context source used by LLM answer synthesis."""

    title: str
    route_path: str
    excerpt: str
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "route_path": self.route_path,
            "excerpt": self.excerpt,
            "score": self.score,
        }


@dataclass(frozen=True)
class KnowledgeAnswer:
    """LLM answer result with source attribution and provider metadata."""

    question: str
    answer: str
    provider: str
    mode: str
    sources: tuple[KnowledgeSource, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "provider": self.provider,
            "mode": self.mode,
            "sources": [item.as_dict() for item in self.sources],
            "metadata": dict(self.metadata),
        }


def slug_to_space_key(route_path: str) -> str:
    parts = [part for part in route_path.strip("/").split("/") if part]
    slug = parts[1] if len(parts) > 1 and parts[0] == "cms" else (parts[0] if parts else "root")
    clean = _SPACE_KEY_RE.sub("-", slug.casefold()).strip("-")
    return clean or "root"


def extract_knowledge_links(text: str) -> tuple[str, ...]:
    """Extract local wiki links and CMS links from a document body."""

    links: set[str] = set()
    for match in _WIKI_LINK_RE.finditer(text or ""):
        target = match.group(1).strip().strip("/")
        if target:
            links.add(f"/cms/{target}" if not target.startswith("/cms/") else target)
    for pattern in (_MARKDOWN_LINK_RE, _CMS_PATH_RE):
        for match in pattern.finditer(text or ""):
            target = match.group(1).rstrip(".,;:")
            if target:
                links.add(target.rstrip("/") or "/cms")
    return tuple(sorted(links))
