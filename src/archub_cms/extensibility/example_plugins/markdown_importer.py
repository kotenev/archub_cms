"""Example plugin: a Markdown importer (Wiki.js/Obsidian-style ingestion).

Implements :class:`ImporterExt`. ``import_documents`` accepts either a markdown
string or a list of ``{"path": ..., "content": ...}`` items and returns
normalized document dicts (front-matter parsed, title derived from front matter
or the first ``# heading``), ready to become knowledge articles.
"""

from __future__ import annotations

__all__ = ["MarkdownImporterPlugin"]

import re
from typing import Any

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                meta[key.strip()] = [
                    item.strip() for item in value[1:-1].split(",") if item.strip()
                ]
            else:
                meta[key.strip()] = value
    return meta, match.group(2)


def _to_document(content: str, *, path: str = "") -> dict[str, Any]:
    front_matter, body = _parse_front_matter(content)
    heading = _HEADING_RE.search(body)
    title = str(front_matter.get("title") or (heading.group(1).strip() if heading else "")) or (
        path.rsplit("/", 1)[-1].removesuffix(".md") or "Untitled"
    )
    tags = front_matter.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return {
        "title": title,
        "body": body.strip(),
        "front_matter": front_matter,
        "tags": tags or [],
        "source_path": path,
    }


class MarkdownImporterPlugin:
    name = "markdown"

    def import_documents(self, source: Any) -> list[dict[str, Any]]:
        if isinstance(source, str):
            return [_to_document(source)]
        documents: list[dict[str, Any]] = []
        for item in source or ():
            if isinstance(item, dict):
                documents.append(
                    _to_document(str(item.get("content") or ""), path=str(item.get("path") or ""))
                )
            elif isinstance(item, str):
                documents.append(_to_document(item))
        return documents
