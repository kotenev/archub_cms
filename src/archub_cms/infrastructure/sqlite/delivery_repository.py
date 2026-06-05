"""Delivery repository adapter.

Maps the legacy service's published-syndication reads (sitemap, feed, tag index,
redirects) to the ``domain.delivery`` read models and the ``Redirect`` aggregate.
"""

from __future__ import annotations

__all__ = ["CmsDeliveryRepository"]

from typing import Any

from archub_cms.domain.delivery.read_models import FeedItem, SitemapEntry, TagBucket
from archub_cms.domain.delivery.redirect import Redirect
from archub_cms.services.cms import ArcHubCMSService, ContentRedirect, get_archub_cms_service


def _redirect(redirect: ContentRedirect) -> Redirect:
    return Redirect(
        redirect_id=redirect.redirect_id,
        source_path=redirect.source_path,
        target_path=redirect.target_path,
        status_code=redirect.status_code,
        active=redirect.active,
        note=redirect.note,
    )


class CmsDeliveryRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def sitemap(self, *, base_url: str = "") -> list[SitemapEntry]:
        return [
            SitemapEntry(loc=row["loc"], lastmod=row["lastmod"], priority=row["priority"])
            for row in self._cms.published_sitemap(base_url=base_url)
        ]

    def feed(self, *, base_url: str = "", limit: int = 25) -> list[FeedItem]:
        return [
            FeedItem(
                title=str(row.get("title") or ""),
                description=str(row.get("description") or ""),
                link=str(row.get("link") or ""),
                guid=str(row.get("guid") or ""),
                published_at_iso=str(row.get("published_at_iso") or ""),
                tags=tuple(row.get("tags") or ()),
                content_type_alias=str(row.get("content_type_alias") or ""),
            )
            for row in self._cms.published_feed(base_url=base_url, limit=limit)
        ]

    def tag_index(self) -> list[TagBucket]:
        return [
            TagBucket(
                tag=str(row.get("tag") or ""),
                slug=str(row.get("slug") or ""),
                count=int(row.get("count") or 0),
                content_types=dict(row.get("content_types") or {}),
            )
            for row in self._cms.published_tag_index()
        ]

    def by_tag(self, tag: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._cms.published_by_tag(tag, limit=limit)

    def list_redirects(self, *, active_only: bool = False, limit: int = 200) -> list[Redirect]:
        return [
            _redirect(item)
            for item in self._cms.list_redirects(active_only=active_only, limit=limit)
        ]

    def resolve_redirect(self, path: str) -> Redirect | None:
        found = self._cms.resolve_redirect(path)
        return _redirect(found) if found is not None else None
