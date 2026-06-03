"""Published-content facade inspired by Umbraco's published content APIs."""

from __future__ import annotations

__all__ = [
    "ArcHubContentHelper",
    "PublishedContent",
    "get_archub_content_helper",
]

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar, cast

from archub_cms.services.cms import (
    ArcHubCMSService,
    ContentNode,
    MediaAsset,
    get_archub_cms_service,
)
from archub_cms.services.content_builder import (
    ArcHubContentBuilderService,
    get_archub_content_builder_service,
)

T = TypeVar("T")


@dataclass(frozen=True)
class PublishedContent:
    """Typed view over the published JSON payload for one CMS node.

    The object keeps route/tree metadata next to the localized payload and gives
    templates/integrations a small, stable API instead of direct dictionary
    indexing. It intentionally resembles Umbraco's `IPublishedContent` concepts
    without coupling ArcHub to Umbraco internals.
    """

    node: ContentNode
    payload: dict[str, Any]
    cms: ArcHubCMSService = field(repr=False, compare=False)
    culture: str = ""
    segment: str = ""

    @property
    def node_id(self) -> str:
        return self.node.node_id

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def content_type_alias(self) -> str:
        return self.node.content_type_alias

    @property
    def route_path(self) -> str:
        return self.node.route_path

    @property
    def parent_id(self) -> str | None:
        return self.node.parent_id

    @property
    def level(self) -> int:
        return self.node.level

    @property
    def published_at(self) -> float | None:
        return self.node.published_at

    @property
    def updated_at(self) -> float:
        return self.node.updated_at

    def url(self) -> str:
        return self.node.route_path

    def value(
        self, alias: str, default: T | None = None, *, expected_type: type[T] | None = None
    ) -> T | Any:
        value = self.payload.get(alias, default)
        if expected_type is not None and value is not None and not isinstance(value, expected_type):
            return default
        return value

    def has_value(self, alias: str) -> bool:
        value = self.payload.get(alias)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return bool(value)
        return True

    def children(self) -> list[PublishedContent]:
        return [
            PublishedContent.from_node(child, self.cms, culture=self.culture, segment=self.segment)
            for child in self.cms.published_children(self.node_id)
        ]

    def descendants_or_self(self) -> list[PublishedContent]:
        items = [self]
        for child in self.children():
            items.extend(child.descendants_or_self())
        return items

    def as_delivery_payload(self, *, include_children: bool = False) -> dict[str, Any]:
        payload = self.cms.published_content_payload(
            self.route_path,
            include_children=include_children,
            culture=self.culture,
            segment=self.segment,
        )
        return payload or {}

    @classmethod
    def from_node(
        cls,
        node: ContentNode,
        cms: ArcHubCMSService,
        *,
        culture: str = "",
        segment: str = "",
    ) -> PublishedContent:
        delivery = cms.published_content_payload(
            node.route_path,
            culture=culture,
            segment=segment,
        )
        payload = (
            delivery.get("payload", {}) if isinstance(delivery, dict) else dict(node.published)
        )
        return cls(
            node=node,
            payload=dict(payload),
            cms=cms,
            culture=str(delivery.get("culture", culture))
            if isinstance(delivery, dict)
            else culture,
            segment=str(delivery.get("segment", segment))
            if isinstance(delivery, dict)
            else segment,
        )


class ArcHubContentHelper:
    """Developer-facing helper for published content, media, dictionary and blocks."""

    def __init__(
        self,
        cms: ArcHubCMSService | None = None,
        builder: ArcHubContentBuilderService | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._builder = builder or get_archub_content_builder_service()

    def content(
        self,
        node_id_or_path: str,
        *,
        culture: str = "",
        segment: str = "",
    ) -> PublishedContent | None:
        key = node_id_or_path.strip()
        if not key:
            return None
        node = self._cms.get_node(key) if not key.startswith("/") else None
        if node is None:
            node = self._cms.get_published_by_path(key)
        if node is None or not node.is_published:
            return None
        return PublishedContent.from_node(node, self._cms, culture=culture, segment=segment)

    def query(
        self,
        *,
        content_type_alias: str = "",
        tag: str = "",
        limit: int = 100,
        culture: str = "",
        segment: str = "",
    ) -> list[PublishedContent]:
        return [
            item
            for result in self._cms.published_search(
                content_type_alias=content_type_alias,
                tag=tag,
                limit=limit,
                culture=culture,
                segment=segment,
            )
            for item in [
                self.content(str(result.get("route_path", "")), culture=culture, segment=segment)
            ]
            if item is not None
        ]

    def media(self, asset_id: str) -> MediaAsset | None:
        clean = asset_id.strip()
        if not clean:
            return None
        for asset in self._cms.list_media_assets(limit=500):
            if asset.asset_id == clean:
                return asset
        return None

    def media_by_url(self, url: str) -> MediaAsset | None:
        clean = url.strip()
        if not clean:
            return None
        for asset in self._cms.list_media_assets(limit=500):
            if asset.url == clean:
                return asset
        return None

    def dictionary_value(self, item_key: str, *, culture: str = "", default: str = "") -> str:
        key = item_key.strip()
        if not key:
            return default
        for item in self._cms.list_dictionary_items(limit=500):
            if str(item.get("item_key", "")) != key:
                continue
            values = cast(dict[str, Any], item.get("values") or {})
            return _culture_value(values, culture, default)
        return default

    def render_blocks(self, value: Any, *, strict: bool = False) -> str:
        return self._builder.render_blocks(self._builder.parse_blocks(value, strict=strict))

    def render_content_blocks(
        self,
        content: PublishedContent,
        *,
        field_aliases: Iterable[str] = ("builder_blocks", "blocks"),
    ) -> str:
        for alias in field_aliases:
            if content.has_value(alias):
                return self.render_blocks(content.value(alias))
        return ""


def get_archub_content_helper(
    cms: ArcHubCMSService | None = None,
    builder: ArcHubContentBuilderService | None = None,
) -> ArcHubContentHelper:
    return ArcHubContentHelper(cms=cms, builder=builder)


def _culture_value(values: dict[str, Any], culture: str, default: str) -> str:
    clean = culture.strip()
    candidates = [clean]
    if "-" in clean:
        candidates.append(clean.split("-", 1)[0])
    candidates.extend(["", "default", "invariant"])
    for candidate in candidates:
        if candidate in values:
            return str(values[candidate])
    return default
