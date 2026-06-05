"""Application service for delivery syndication + redirect management.

``DeliveryReadService`` serves sitemap/feed/tag-index/redirect read models from
the :class:`DeliveryRepository`. ``RedirectCommandService`` validates a
:class:`Redirect` against domain invariants, persists via the legacy service, and
publishes ``delivery.redirect.upserted`` to the kernel bus.
"""

from __future__ import annotations

__all__ = [
    "DeliveryReadService",
    "RedirectCommandService",
    "get_archub_delivery_read_service",
]

from typing import Any

from archub_cms.domain.delivery.redirect import Redirect
from archub_cms.domain.delivery.repository import DeliveryRepository
from archub_cms.infrastructure.sqlite.delivery_repository import CmsDeliveryRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class DeliveryReadService:
    def __init__(self, repository: DeliveryRepository) -> None:
        self._repo = repository

    def sitemap(self, *, base_url: str = "") -> dict[str, Any]:
        items = self._repo.sitemap(base_url=base_url)
        return {"items": [i.as_dict() for i in items], "total": len(items)}

    def feed(self, *, base_url: str = "", limit: int = 25) -> dict[str, Any]:
        items = self._repo.feed(base_url=base_url, limit=limit)
        return {"items": [i.as_dict() for i in items], "total": len(items)}

    def tags(self) -> dict[str, Any]:
        items = self._repo.tag_index()
        return {"items": [i.as_dict() for i in items], "total": len(items)}

    def by_tag(self, tag: str, *, limit: int = 50) -> dict[str, Any]:
        items = self._repo.by_tag(tag, limit=limit)
        return {"tag": tag, "items": items, "total": len(items)}

    def redirects(self, *, active_only: bool = False, limit: int = 200) -> dict[str, Any]:
        items = self._repo.list_redirects(active_only=active_only, limit=limit)
        return {"items": [i.as_dict() for i in items], "total": len(items)}

    def resolve(self, path: str) -> dict[str, Any] | None:
        found = self._repo.resolve_redirect(path)
        return found.as_dict() if found is not None else None


class RedirectCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: DeliveryRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsDeliveryRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def upsert_redirect(
        self,
        *,
        source_path: str,
        target_path: str,
        status_code: int = 301,
        active: bool = True,
        note: str = "",
        actor: str,
    ) -> Redirect:
        candidate = Redirect(
            redirect_id="",
            source_path=source_path,
            target_path=target_path,
            status_code=status_code,
            active=active,
            note=note,
        )
        errors = candidate.validate()
        if errors:
            raise ValueError("; ".join(errors))

        stored = self._cms.upsert_redirect(
            source_path=source_path,
            target_path=target_path,
            status_code=status_code,
            active=active,
            note=note,
            updated_by=actor,
        )
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="delivery.redirect.upserted",
                aggregate_id=stored.redirect_id,
                actor=actor,
                metadata={
                    "source_path": stored.source_path,
                    "target_path": stored.target_path,
                    "status_code": stored.status_code,
                },
            )
        )
        return Redirect(
            redirect_id=stored.redirect_id,
            source_path=stored.source_path,
            target_path=stored.target_path,
            status_code=stored.status_code,
            active=stored.active,
            note=stored.note,
        )


def get_archub_delivery_read_service(
    *, cms: ArcHubCMSService | None = None, repository: DeliveryRepository | None = None
) -> DeliveryReadService:
    return DeliveryReadService(repository or CmsDeliveryRepository(cms))
