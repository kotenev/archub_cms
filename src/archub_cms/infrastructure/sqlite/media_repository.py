"""Media repository adapter mapping legacy media reads to the domain aggregate."""

from __future__ import annotations

__all__ = ["CmsMediaRepository"]

from archub_cms.domain.media.asset import MediaAsset
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service
from archub_cms.services.cms import MediaAsset as LegacyMediaAsset


def _asset(asset: LegacyMediaAsset) -> MediaAsset:
    return MediaAsset(
        asset_id=asset.asset_id,
        filename=asset.filename,
        content_type=asset.content_type,
        url=asset.url,
        original_name=asset.original_name,
        folder=asset.folder,
        alt_text=asset.alt_text,
        tags=tuple(asset.tags),
        metadata=dict(asset.metadata),
        created_at=asset.created_at,
        created_by=asset.created_by,
    )


class CmsMediaRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def list_assets(self, *, folder: str = "", limit: int = 100) -> list[MediaAsset]:
        return [_asset(a) for a in self._cms.list_media_assets(folder=folder, limit=limit)]
