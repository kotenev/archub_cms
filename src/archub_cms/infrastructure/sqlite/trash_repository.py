"""Trash repository adapter mapping legacy recycle-bin reads to read models."""

from __future__ import annotations

__all__ = ["CmsTrashRepository"]

from archub_cms.domain.trash.item import TrashedItem
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class CmsTrashRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def list_trashed(self, *, limit: int = 100) -> list[TrashedItem]:
        return [TrashedItem.from_payload(p) for p in self._cms.list_trashed_nodes(limit=limit)]
