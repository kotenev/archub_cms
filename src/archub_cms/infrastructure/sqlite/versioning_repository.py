"""Versioning repository adapter mapping legacy version reads to domain models."""

from __future__ import annotations

__all__ = ["CmsVersioningRepository"]

from archub_cms.domain.versioning.version import Version
from archub_cms.services.cms import ArcHubCMSService, ContentVersion, get_archub_cms_service


def _version(version: ContentVersion) -> Version:
    return Version(
        version_id=version.version_id,
        node_id=version.node_id,
        version_no=version.version_no,
        status=version.status,
        payload=dict(version.payload),
        created_at=version.created_at,
        created_by=version.created_by,
        note=version.note,
    )


class CmsVersioningRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def history(self, node_id: str, *, limit: int = 20) -> list[Version]:
        return [_version(v) for v in self._cms.list_versions(node_id, limit=limit)]

    def get(self, node_id: str, version_no: int) -> Version | None:
        for version in self._cms.list_versions(node_id, limit=500):
            if version.version_no == version_no:
                return _version(version)
        return None
