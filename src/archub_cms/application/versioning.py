"""Content versioning application service for ArcHub CMS."""

from __future__ import annotations

__all__ = [
    "VersioningOperationResult",
    "ArcHubVersioningService",
    "get_archub_versioning_service",
]

from dataclasses import dataclass
from typing import Any

from archub_cms.domain.events import ArcHubDomainEvent, content_event
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service

_DEFAULT_VERSION_RETENTION_SECONDS = 60.0 * 60.0 * 24.0 * 90.0


@dataclass(frozen=True)
class VersioningOperationResult:
    """Result envelope for content history use cases."""

    payload: dict[str, Any]
    events: tuple[ArcHubDomainEvent, ...] = ()
    status_code: int = 200

    def as_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        if not include_events:
            return self.payload
        return {
            **self.payload,
            "events": [event.as_dict() for event in self.events],
        }


class ArcHubVersioningService:
    """Application boundary for version history, restore, and retention cleanup."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def versions(self, node_id: str, *, limit: int = 20) -> dict[str, Any]:
        items = self._cms.list_versions(node_id, limit=limit)
        return {
            "node_id": node_id,
            "items": [item.__dict__ for item in items],
            "total": len(items),
        }

    def version(
        self, node_id: str, version_no: int, *, limit: int = 500
    ) -> VersioningOperationResult:
        for version in self._cms.list_versions(node_id, limit=limit):
            if version.version_no == version_no:
                return VersioningOperationResult(payload=version.__dict__)
        return VersioningOperationResult(
            payload={
                "error": "Content version not found",
                "node_id": node_id,
                "version_no": version_no,
            },
            status_code=404,
        )

    def restore(self, node_id: str, version_no: int, *, actor: str) -> VersioningOperationResult:
        node = self._cms.restore_version(node_id, version_no, updated_by=actor)
        return VersioningOperationResult(
            payload={
                "ok": True,
                "node": node.__dict__,
                "node_id": node.node_id,
                "version_no": version_no,
            },
            events=(
                content_event(
                    "content.version.restored",
                    node_id=node.node_id,
                    actor=actor,
                    metadata={
                        "version_no": version_no,
                        "route_path": node.route_path,
                        "content_type_alias": node.content_type_alias,
                    },
                ),
            ),
        )

    def cleanup(
        self,
        *,
        node_id: str = "",
        keep_latest: int = 20,
        older_than_seconds: float | None = _DEFAULT_VERSION_RETENTION_SECONDS,
        actor: str = "system",
    ) -> VersioningOperationResult:
        payload = self._cms.cleanup_content_versions(
            node_id=node_id,
            keep_latest=keep_latest,
            older_than_seconds=older_than_seconds,
            actor=actor,
        )
        return VersioningOperationResult(
            payload=payload,
            events=(
                content_event(
                    "content.versions.cleaned",
                    node_id=node_id or "content_versions",
                    actor=actor,
                    metadata={
                        "deleted_count": payload["deleted_count"],
                        "examined_nodes": payload["examined_nodes"],
                        "keep_latest": payload["keep_latest"],
                        "older_than_seconds": payload["older_than_seconds"],
                    },
                ),
            ),
        )


def get_archub_versioning_service(cms: ArcHubCMSService | None = None) -> ArcHubVersioningService:
    return ArcHubVersioningService(cms=cms)
