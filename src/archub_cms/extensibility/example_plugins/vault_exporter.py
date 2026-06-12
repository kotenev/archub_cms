"""Example plugin: an Obsidian-vault exporter.

Implements :class:`ExporterExt`. ``export_documents`` turns document dicts into
Obsidian-compatible markdown files (YAML front matter + ``# title`` + body),
returning ``{"format", "files": [{"path", "content"}], "total"}`` — the offline
knowledge-portability path.
"""

from __future__ import annotations

__all__ = ["VaultExporterPlugin"]

import re
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value.casefold()).strip("-") or "untitled"


def _front_matter(document: dict[str, Any]) -> str:
    lines = ["---"]
    title = str(document.get("title") or "Untitled")
    lines.append(f"title: {title}")
    tags = document.get("tags") or []
    if tags:
        lines.append(f"tags: [{', '.join(str(t) for t in tags)}]")
    if document.get("route_path"):
        lines.append(f"route_path: {document['route_path']}")
    lines.append("---")
    return "\n".join(lines)


class VaultExporterPlugin:
    name = "obsidian-vault"

    def export_documents(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        files = []
        for document in documents or ():
            title = str(document.get("title") or "Untitled")
            path = str(document.get("markdown_path") or f"{_slug(title)}.md")
            body = str(document.get("body") or document.get("summary") or "")
            content = f"{_front_matter(document)}\n\n# {title}\n\n{body.strip()}\n"
            files.append({"path": path, "content": content})
        return {
            "format": "obsidian-compatible-markdown-vault",
            "files": files,
            "total": len(files),
        }
