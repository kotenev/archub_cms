"""Example plugin: a backlinks/recent-publications connector.

Demonstrates a real, executable in-process plugin:

* implements ``setup`` and registers itself as both an event hook and a search
  extension;
* subscribes to ``content.published`` and maintains an in-memory index of
  published routes (no DB access — it must not re-enter the write path);
* contributes :class:`SearchHit` results from that index.

Loaded via the manifest at ``plugins/example_backlinks/plugin.json``.
"""

from __future__ import annotations

__all__ = ["BacklinksPlugin"]

from archub_cms.domain.content.events import CONTENT_PUBLISHED
from archub_cms.extensibility.extension_points import PluginContext, SearchHit
from archub_cms.kernel.events import ArcHubDomainEvent


class BacklinksPlugin:
    event_types = (CONTENT_PUBLISHED,)

    def __init__(self) -> None:
        self.published: dict[str, str] = {}  # route_path -> title/summary
        self.events_seen = 0

    def setup(self, context: PluginContext) -> None:
        # Register self as the extension; the host wires our event_types to the bus.
        context.register(self)

    def handle(self, event: ArcHubDomainEvent) -> None:
        self.events_seen += 1
        metadata = event.metadata or {}
        route = str(metadata.get("route_path") or "")
        if route:
            self.published[route] = str(
                metadata.get("node_name") or metadata.get("summary") or route
            )

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        tokens = [t for t in query.casefold().split() if t]
        hits: list[SearchHit] = []
        for route, title in self.published.items():
            haystack = f"{route} {title}".casefold()
            score = sum(1.0 for token in tokens if token in haystack) if tokens else 0.5
            if score:
                hits.append(
                    SearchHit(
                        route_path=route,
                        title=title,
                        excerpt=f"Recently published: {title}",
                        score=score,
                        source="example.backlinks",
                    )
                )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]
