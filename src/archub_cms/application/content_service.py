"""Application service for the content bounded context (CQRS-lite).

``ContentQueryService`` serves reads from the :class:`ContentRepository`;
``ContentService`` runs commands. Writes are still executed by the legacy
``ArcHubCMSService`` (whose node lifecycle is deeply entangled with content-type
validation, payload cleaning and versioning); this service is the DDD front door
that returns domain aggregates and guarantees domain events reach the
:class:`EventBus`. Later phases move the write SQL into a command repository.
"""

from __future__ import annotations

__all__ = [
    "ContentQueryService",
    "ContentService",
    "get_archub_content_service",
]

from typing import Any

from archub_cms.domain.content.node import ContentNode
from archub_cms.domain.content.repository import ContentRepository
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.content_repository import SqliteContentRepository
from archub_cms.kernel.events import EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class ContentQueryService:
    """Read side: queries over the content tree returning domain aggregates."""

    def __init__(self, repository: ContentRepository) -> None:
        self._repository = repository

    def get_node(self, node_id: str) -> ContentNode | None:
        return self._repository.get(node_id)

    def get_by_route(self, route_path: str) -> ContentNode | None:
        return self._repository.get_by_route(route_path)

    def tree(self, *, include_trashed: bool = False) -> list[ContentNode]:
        return self._repository.list_tree(include_trashed=include_trashed)

    def children(self, parent_id: str | None) -> list[ContentNode]:
        return self._repository.children(parent_id)

    def published_documents(self) -> list[ContentNode]:
        return [node for node in self._repository.list_tree() if node.is_published]


class ContentService:
    """Write side: commands that enforce domain invariants and emit events."""

    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: ContentRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repository = repository or SqliteContentRepository(Database(self._cms.db_path))
        self._bus = event_bus or get_event_bus()
        self.queries = ContentQueryService(self._repository)

    def create_node(
        self,
        *,
        parent_id: str | None,
        content_type_alias: str,
        name: str,
        slug: str,
        payload: dict[str, Any],
        created_by: str,
    ) -> ContentNode:
        legacy = self._cms.create_node(
            parent_id=parent_id,
            content_type_alias=content_type_alias,
            name=name,
            slug=slug,
            payload=payload,
            created_by=created_by,
        )
        node = self._repository.get(legacy.node_id)
        assert node is not None
        return node

    def update_node(
        self, node_id: str, *, name: str, slug: str, payload: dict[str, Any], updated_by: str
    ) -> ContentNode:
        self._cms.update_node(node_id, name=name, slug=slug, payload=payload, updated_by=updated_by)
        node = self._repository.get(node_id)
        assert node is not None
        return node

    def publish_node(self, node_id: str, *, published_by: str) -> ContentNode:
        node = self._repository.get(node_id)
        if node is not None and not node.is_root:
            guard = node.can_publish()
            if not guard.ok:
                raise ValueError(getattr(guard, "error", "node is not publishable"))
        self._cms.publish_node(node_id, published_by=published_by)
        published = self._repository.get(node_id)
        assert published is not None
        return published

    def delete_node(self, node_id: str, *, deleted_by: str = "") -> None:
        self._cms.delete_node(node_id, deleted_by=deleted_by)


def get_archub_content_service(
    *,
    cms: ArcHubCMSService | None = None,
    repository: ContentRepository | None = None,
    event_bus: EventBus | None = None,
) -> ContentService:
    return ContentService(cms=cms, repository=repository, event_bus=event_bus)
