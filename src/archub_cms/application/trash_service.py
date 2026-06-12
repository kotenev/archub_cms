"""Application service for the trash / recycle-bin context.

``TrashQueryService`` lists the recycle bin. ``TrashCommandService`` restores an
item to its original location, purges one permanently, or empties the bin —
delegating to the legacy service and emitting domain events.
"""

from __future__ import annotations

__all__ = [
    "TrashCommandService",
    "TrashItemNotFoundError",
    "TrashQueryService",
    "get_archub_trash_query_service",
]

from typing import Any

from archub_cms.domain.trash.repository import TrashRepository
from archub_cms.infrastructure.sqlite.trash_repository import CmsTrashRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class TrashItemNotFoundError(LookupError):
    """Raised when restoring/purging a node that is not in the recycle bin."""


class TrashQueryService:
    def __init__(self, repository: TrashRepository) -> None:
        self._repo = repository

    def items(self, *, limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_trashed(limit=limit)
        return {"items": [i.as_dict() for i in items], "total": len(items)}


class TrashCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: TrashRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsTrashRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def restore(self, node_id: str, *, actor: str) -> dict[str, Any]:
        try:
            node = self._cms.restore_trashed_node(node_id, restored_by=actor)
        except ValueError as exc:
            raise TrashItemNotFoundError(node_id) from exc
        # Namespaced distinctly from the legacy activity action
        # "content.restored_from_trash" so subscribers get exactly one event.
        self._bus.publish(
            ArcHubDomainEvent(
                "trash.item.restored", node_id, actor, {"route_path": node.route_path}
            )
        )
        return {"node_id": node_id, "route_path": node.route_path, "status": node.status}

    def purge(self, node_id: str, *, actor: str) -> dict[str, Any]:
        try:
            self._cms.purge_trashed_node(node_id, purged_by=actor)
        except ValueError as exc:
            raise TrashItemNotFoundError(node_id) from exc
        # Distinct from the legacy activity action "content.purged".
        self._bus.publish(ArcHubDomainEvent("trash.item.purged", node_id, actor, {}))
        return {"node_id": node_id, "purged": True}

    def empty(self, *, actor: str) -> dict[str, Any]:
        purged: list[str] = []
        for item in self._repo.list_trashed(limit=500):
            try:
                self._cms.purge_trashed_node(item.node_id, purged_by=actor)
                purged.append(item.node_id)
            except ValueError:
                continue
        if purged:
            self._bus.publish(
                ArcHubDomainEvent("trash.emptied", "", actor, {"purged": len(purged)})
            )
        return {"purged": purged, "purged_count": len(purged)}


def get_archub_trash_query_service(
    *, cms: ArcHubCMSService | None = None, repository: TrashRepository | None = None
) -> TrashQueryService:
    return TrashQueryService(repository or CmsTrashRepository(cms))
