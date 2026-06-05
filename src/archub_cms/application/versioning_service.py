"""Application service for the versioning context (history, diff, restore).

``VersioningQueryService`` serves history and computes field-level diffs between
two versions. ``VersioningCommandService`` restores a node to a prior version via
the legacy service and publishes ``content.version.restored`` to the kernel bus.
"""

from __future__ import annotations

__all__ = [
    "VersionNotFoundError",
    "VersioningCommandService",
    "VersioningQueryService",
    "get_archub_versioning_query_service",
]

from typing import Any

from archub_cms.domain.versioning.diff import VersionDiff
from archub_cms.domain.versioning.repository import VersioningRepository
from archub_cms.infrastructure.sqlite.versioning_repository import CmsVersioningRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class VersionNotFoundError(LookupError):
    """Raised when a requested version number does not exist for a node."""


class VersioningQueryService:
    def __init__(self, repository: VersioningRepository) -> None:
        self._repo = repository

    def history(self, node_id: str, *, limit: int = 20) -> dict[str, Any]:
        versions = self._repo.history(node_id, limit=limit)
        return {
            "node_id": node_id,
            "items": [v.as_dict() for v in versions],
            "total": len(versions),
        }

    def diff(self, node_id: str, *, from_version_no: int, to_version_no: int) -> dict[str, Any]:
        from_version = self._repo.get(node_id, from_version_no)
        to_version = self._repo.get(node_id, to_version_no)
        if from_version is None:
            raise VersionNotFoundError(f"{node_id}@{from_version_no}")
        if to_version is None:
            raise VersionNotFoundError(f"{node_id}@{to_version_no}")
        return VersionDiff.between(from_version, to_version).as_dict()


class VersioningCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: VersioningRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsVersioningRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def restore(self, node_id: str, version_no: int, *, actor: str) -> dict[str, Any]:
        if self._repo.get(node_id, version_no) is None:
            raise VersionNotFoundError(f"{node_id}@{version_no}")
        node = self._cms.restore_version(node_id, version_no, updated_by=actor)
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="content.version.restored",
                aggregate_id=node_id,
                actor=actor,
                metadata={"version_no": version_no, "route_path": node.route_path},
            )
        )
        return {
            "node_id": node_id,
            "restored_version_no": version_no,
            "status": node.status,
            "route_path": node.route_path,
        }


def get_archub_versioning_query_service(
    *, cms: ArcHubCMSService | None = None, repository: VersioningRepository | None = None
) -> VersioningQueryService:
    return VersioningQueryService(repository or CmsVersioningRepository(cms))
