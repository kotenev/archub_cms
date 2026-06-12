"""Application service for the localization / i18n context.

``LocalizationQueryService`` reads variants, available cultures, the dictionary,
and resolves translations with locale fallback. ``LocalizationCommandService``
upserts/publishes culture variants and dictionary entries (validating the
``Culture`` value object) and emits domain events.
"""

from __future__ import annotations

__all__ = [
    "LocalizationCommandService",
    "LocalizationQueryService",
    "get_archub_localization_query_service",
]

from typing import Any

from archub_cms.domain.content.value_objects import Culture
from archub_cms.domain.localization.repository import LocalizationRepository
from archub_cms.infrastructure.sqlite.localization_repository import CmsLocalizationRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class LocalizationQueryService:
    def __init__(self, repository: LocalizationRepository) -> None:
        self._repo = repository

    def variants(self, node_id: str) -> dict[str, Any]:
        items = self._repo.variants(node_id)
        return {"node_id": node_id, "items": [v.as_dict() for v in items], "total": len(items)}

    def cultures(self, node_id: str) -> dict[str, Any]:
        items = self._repo.variants(node_id)
        return {
            "node_id": node_id,
            "cultures": [v.culture.value for v in items],
            "published_cultures": [v.culture.value for v in items if v.is_published],
        }

    def dictionary(self, *, group: str = "", limit: int = 200) -> dict[str, Any]:
        items = self._repo.dictionary(group=group, limit=limit)
        return {"items": [e.as_dict() for e in items], "total": len(items)}

    def translate(
        self, key: str, *, culture: str = "", group: str = "", default: str = ""
    ) -> dict[str, Any]:
        entry = self._repo.dictionary_entry(key, group=group)
        value = entry.resolve(culture, default=default) if entry is not None else default
        return {"key": key, "culture": culture, "value": value, "found": entry is not None}


class LocalizationCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: LocalizationRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsLocalizationRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def upsert_variant(
        self, node_id: str, *, culture: str, payload: dict[str, Any], actor: str
    ) -> dict[str, Any]:
        parsed = Culture.parse(culture)  # validates the culture code
        if parsed.is_invariant:
            raise ValueError("culture is required for a localized variant")
        self._cms.upsert_content_variant(
            node_id, culture=parsed.value, payload=payload, updated_by=actor
        )
        self._bus.publish(
            ArcHubDomainEvent(
                "localization.variant.upserted", node_id, actor, {"culture": parsed.value}
            )
        )
        variant = self._repo.variant(node_id, parsed.value)
        assert variant is not None
        return variant.as_dict()

    def publish_variant(self, node_id: str, *, culture: str, actor: str) -> dict[str, Any]:
        parsed = Culture.parse(culture)
        self._cms.publish_content_variant(node_id, culture=parsed.value, published_by=actor)
        self._bus.publish(
            ArcHubDomainEvent(
                "localization.variant.published", node_id, actor, {"culture": parsed.value}
            )
        )
        variant = self._repo.variant(node_id, parsed.value)
        assert variant is not None
        return variant.as_dict()

    def upsert_dictionary(
        self, *, key: str, group: str, values: dict[str, str], actor: str
    ) -> dict[str, Any]:
        if not key.strip():
            raise ValueError("dictionary key is required")
        if not values:
            raise ValueError("at least one locale value is required")
        self._cms.upsert_dictionary_item(
            item_key=key, group_name=group, values=values, updated_by=actor
        )
        self._bus.publish(
            ArcHubDomainEvent("localization.dictionary.upserted", key, actor, {"group": group})
        )
        entry = self._repo.dictionary_entry(key, group=group)
        return (
            entry.as_dict() if entry is not None else {"key": key, "group": group, "values": values}
        )


def get_archub_localization_query_service(
    *, cms: ArcHubCMSService | None = None, repository: LocalizationRepository | None = None
) -> LocalizationQueryService:
    return LocalizationQueryService(repository or CmsLocalizationRepository(cms))
