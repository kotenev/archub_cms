"""Bulk content ingestion — import a markdown corpus into the knowledge base.

Composes the plugin **importer** (``ImporterExt``, e.g. the bundled markdown
importer) with the content context: a source (a markdown string, or a list of
``{"path", "content"}`` items — an Obsidian vault / Wiki.js export) is parsed
into normalized documents and each becomes a content node, optionally published.
Per-document failures are collected, never aborting the batch.
"""

from __future__ import annotations

__all__ = ["IngestionService", "get_archub_ingestion_service"]

from typing import Any

from archub_cms.application.content_service import ContentService, get_archub_content_service
from archub_cms.extensibility.host import PluginHost, get_plugin_host
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus


class IngestionService:
    def __init__(
        self,
        *,
        content: ContentService | None = None,
        plugin_host: PluginHost | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._content = content or get_archub_content_service()
        self._host = plugin_host or get_plugin_host()
        self._bus = event_bus or get_event_bus()

    def import_markdown(
        self,
        source: Any,
        *,
        importer: str = "markdown",
        parent_id: str = "root",
        content_type_alias: str = "page",
        publish: bool = False,
        actor: str = "system",
    ) -> dict[str, Any]:
        try:
            documents = self._host.import_documents(importer, source)
        except KeyError as exc:
            raise ValueError(f"unknown importer: {importer}") from exc

        created: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for doc in documents:
            try:
                node = self._content.create_node(
                    parent_id=parent_id,
                    content_type_alias=content_type_alias,
                    name=str(doc.get("title") or "Untitled"),
                    slug="",
                    payload=_payload(doc),
                    created_by=actor,
                )
                if publish:
                    self._content.publish_node(node.node_id, published_by=actor)
                created.append({"node_id": node.node_id, "route_path": node.route_path.value})
            except Exception as exc:  # one bad doc must not abort the batch
                failed.append({"title": doc.get("title"), "error": str(exc)})

        self._bus.publish(
            ArcHubDomainEvent(
                "ingestion.completed",
                parent_id,
                actor,
                {"importer": importer, "created": len(created), "failed": len(failed)},
            )
        )
        return {
            "importer": importer,
            "documents": len(documents),
            "created": created,
            "created_count": len(created),
            "failed": failed,
            "published": publish,
        }


def _payload(doc: dict[str, Any]) -> dict[str, Any]:
    tags = doc.get("tags") or []
    return {
        "title": str(doc.get("title") or "Untitled"),
        "body": str(doc.get("body") or ""),
        "summary": str(doc.get("body") or "")[:280],
        "tags": ",".join(str(t) for t in tags) if isinstance(tags, list) else str(tags),
        "source_path": str(doc.get("source_path") or ""),
    }


def get_archub_ingestion_service(
    *,
    content: ContentService | None = None,
    plugin_host: PluginHost | None = None,
) -> IngestionService:
    return IngestionService(content=content, plugin_host=plugin_host)
