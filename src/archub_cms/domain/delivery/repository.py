"""Repository port for the delivery context."""

from __future__ import annotations

__all__ = ["DeliveryRepository"]

from typing import Any, Protocol, runtime_checkable

from archub_cms.domain.delivery.read_models import FeedItem, SitemapEntry, TagBucket
from archub_cms.domain.delivery.redirect import Redirect


@runtime_checkable
class DeliveryRepository(Protocol):
    def sitemap(self, *, base_url: str = "") -> list[SitemapEntry]: ...

    def feed(self, *, base_url: str = "", limit: int = 25) -> list[FeedItem]: ...

    def tag_index(self) -> list[TagBucket]: ...

    def by_tag(self, tag: str, *, limit: int = 50) -> list[dict[str, Any]]: ...

    def list_redirects(self, *, active_only: bool = False, limit: int = 200) -> list[Redirect]: ...

    def resolve_redirect(self, path: str) -> Redirect | None: ...
