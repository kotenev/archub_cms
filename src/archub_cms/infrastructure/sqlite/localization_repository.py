"""Localization repository adapter mapping legacy variant/dictionary reads."""

from __future__ import annotations

__all__ = ["CmsLocalizationRepository"]

from typing import Any

from archub_cms.domain.content.value_objects import Culture
from archub_cms.domain.localization.dictionary import DictionaryEntry
from archub_cms.domain.localization.variant import LocalizedVariant
from archub_cms.services.cms import ArcHubCMSService, ContentVariant, get_archub_cms_service


def _variant(variant: ContentVariant) -> LocalizedVariant:
    return LocalizedVariant(
        node_id=variant.node_id,
        culture=Culture(str(variant.culture)),
        status=variant.status,
        draft=dict(variant.draft),
        published=dict(variant.published),
        updated_at=variant.updated_at,
        published_at=variant.published_at,
        updated_by=variant.updated_by,
    )


def _entry(item: dict[str, Any]) -> DictionaryEntry:
    values = item.get("values")
    return DictionaryEntry(
        key=str(item.get("item_key") or item.get("key") or ""),
        group=str(item.get("group_name") or item.get("group") or ""),
        values={str(k): str(v) for k, v in values.items()} if isinstance(values, dict) else {},
    )


class CmsLocalizationRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def variants(self, node_id: str) -> list[LocalizedVariant]:
        return [_variant(v) for v in self._cms.list_content_variants(node_id)]

    def variant(self, node_id: str, culture: str) -> LocalizedVariant | None:
        found = self._cms.get_content_variant(node_id, culture)
        return _variant(found) if found is not None else None

    def dictionary(self, *, group: str = "", limit: int = 200) -> list[DictionaryEntry]:
        return [_entry(i) for i in self._cms.list_dictionary_items(group_name=group, limit=limit)]

    def dictionary_entry(self, key: str, *, group: str = "") -> DictionaryEntry | None:
        for entry in self.dictionary(group=group, limit=500):
            if entry.key == key:
                return entry
        return None
