"""Example search indexer plugin demonstrating SearchIndexerExt."""

from __future__ import annotations

from typing import Any

from archub_cms.extensibility.extension_points import SearchIndexerExt


class MemorySearchIndexerPlugin:
    """An in-memory search indexer that demonstrates SearchIndexerExt."""

    def setup(self, context: Any) -> None:
        context.register(MemorySearchIndexer())


class MemorySearchIndexer(SearchIndexerExt):
    indexer_name = "memory-indexer"

    def __init__(self) -> None:
        self._index: dict[str, dict[str, Any]] = {}

    def index(self, route_path: str, content: dict[str, Any]) -> None:
        self._index[route_path] = content

    def remove(self, route_path: str) -> None:
        self._index.pop(route_path, None)

    def rebuild(self, documents: list[dict[str, Any]]) -> int:
        self._index.clear()
        for doc in documents:
            path = doc.get("route_path", "")
            if path:
                self._index[path] = doc
        return len(self._index)
