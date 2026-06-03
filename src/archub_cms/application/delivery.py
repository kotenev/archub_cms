"""Published delivery application service.

This module is the first extraction target from the large CMS service. It owns
API projection rules such as field limiting, shallow/deep content references,
children expansion, and start-item context while delegating persistence to the
existing CMS service.
"""

from __future__ import annotations

__all__ = [
    "DeliveryProjection",
    "DeliveryQuery",
    "ArcHubDeliveryService",
    "get_archub_delivery_service",
]

import re
from dataclasses import dataclass, field
from typing import Any

from archub_cms.services.cms import ArcHubCMSService, ContentNode, get_archub_cms_service

_PROPERTIES_RE = re.compile(r"properties\[(?P<inner>[^\]]+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class DeliveryProjection:
    """Projection contract for published delivery responses."""

    fields: frozenset[str] = frozenset()
    expand: frozenset[str] = frozenset()
    expand_all: bool = False

    @classmethod
    def parse(cls, *, fields: str = "", expand: str = "") -> DeliveryProjection:
        return cls(
            fields=frozenset(_split_aliases(fields)),
            expand=frozenset(_expand_aliases(expand)),
            expand_all=_expand_all(expand),
        )

    @property
    def include_children(self) -> bool:
        return "children" in self.expand

    def should_expand(self, alias: str) -> bool:
        return self.expand_all or alias in self.expand


@dataclass(frozen=True)
class DeliveryQuery:
    """Read query options shared by delivery endpoints."""

    culture: str = ""
    segment: str = ""
    fields: str = ""
    expand: str = ""
    include_children: bool = False
    max_depth: int = 8
    start_item: str = ""
    projection: DeliveryProjection = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "projection",
            DeliveryProjection.parse(fields=self.fields, expand=self.expand),
        )


class ArcHubDeliveryService:
    """Application service for API-first published delivery."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def resolve_start_node_id(self, start_item: str, *, fallback: str = "root") -> str:
        clean = start_item.strip()
        if not clean:
            return fallback
        node = self._cms.get_node(clean)
        if node is None:
            node = self._cms.get_published_by_path(clean)
        if node is None or not node.is_published:
            raise ValueError(f"Delivery start item not found: {start_item}")
        return node.node_id

    def content(self, route_path: str, query: DeliveryQuery) -> dict[str, Any] | None:
        include_children = query.include_children or query.projection.include_children
        payload = self._cms.published_content_payload(
            route_path,
            include_children=include_children,
            culture=query.culture,
            segment=query.segment,
        )
        if payload is None:
            return None
        return self._project_delivery_payload(payload, query.projection)

    def tree(self, query: DeliveryQuery, *, root_node_id: str = "root") -> dict[str, Any]:
        payload = self._cms.published_content_tree(
            max_depth=query.max_depth,
            culture=query.culture,
            segment=query.segment,
            root_node_id=root_node_id,
        )
        return self._project_delivery_payload(payload, query.projection) if payload else {}

    def search(
        self,
        query_text: str = "",
        *,
        content_type_alias: str = "",
        tag: str = "",
        limit: int = 20,
        query: DeliveryQuery | None = None,
    ) -> list[dict[str, Any]]:
        delivery_query = query or DeliveryQuery()
        results = self._cms.published_search(
            query_text,
            content_type_alias=content_type_alias,
            tag=tag,
            limit=limit,
            culture=delivery_query.culture,
            segment=delivery_query.segment,
        )
        if not delivery_query.projection.fields:
            return results
        return [
            {
                key: value
                for key, value in result.items()
                if key in delivery_query.projection.fields
                or key
                in {
                    "node_id",
                    "route_path",
                    "content_type_alias",
                    "score",
                }
            }
            for result in results
        ]

    def _project_delivery_payload(
        self,
        payload: dict[str, Any],
        projection: DeliveryProjection,
        *,
        depth: int = 0,
    ) -> dict[str, Any]:
        clean = dict(payload)
        properties = clean.get("payload")
        if isinstance(properties, dict):
            clean["payload"] = self._project_properties(properties, projection, depth=depth)
        children = clean.get("children")
        if isinstance(children, list):
            clean["children"] = [
                self._project_delivery_payload(child, projection, depth=depth + 1)
                for child in children
                if isinstance(child, dict)
            ]
        return clean

    def _project_properties(
        self,
        properties: dict[str, Any],
        projection: DeliveryProjection,
        *,
        depth: int,
    ) -> dict[str, Any]:
        items = (
            properties.items()
            if not projection.fields
            else ((key, properties[key]) for key in sorted(projection.fields) if key in properties)
        )
        return {
            alias: self._expand_value(alias, value, projection, depth=depth)
            for alias, value in items
        }

    def _expand_value(
        self,
        alias: str,
        value: Any,
        projection: DeliveryProjection,
        *,
        depth: int,
    ) -> Any:
        if depth >= 2 or not projection.should_expand(alias):
            return value
        if isinstance(value, str):
            return self._expand_content_reference(value, projection, depth=depth) or value
        if isinstance(value, list):
            return [self._expand_value(alias, item, projection, depth=depth) for item in value]
        if isinstance(value, dict):
            return {
                key: self._expand_value(str(key), item, projection, depth=depth)
                for key, item in value.items()
            }
        return value

    def _expand_content_reference(
        self,
        value: str,
        projection: DeliveryProjection,
        *,
        depth: int,
    ) -> dict[str, Any] | None:
        clean = value.strip()
        if not clean.startswith("/cms"):
            return None
        node = self._cms.get_published_by_path(clean)
        if node is None:
            return None
        return self._content_reference_payload(node, projection, depth=depth + 1)

    def _content_reference_payload(
        self,
        node: ContentNode,
        projection: DeliveryProjection,
        *,
        depth: int,
    ) -> dict[str, Any]:
        payload = self._cms.published_content_payload(node.route_path) or {}
        result = {
            "node_id": node.node_id,
            "name": node.name,
            "route_path": node.route_path,
            "content_type_alias": node.content_type_alias,
            "url": node.route_path,
        }
        properties = payload.get("payload")
        if isinstance(properties, dict):
            result["payload"] = self._project_properties(
                properties,
                projection,
                depth=depth,
            )
        return result


def get_archub_delivery_service(cms: ArcHubCMSService | None = None) -> ArcHubDeliveryService:
    return ArcHubDeliveryService(cms=cms)


def _split_aliases(value: str) -> list[str]:
    aliases: list[str] = []
    for item in re.split(r"[,;\s]+", value.strip()):
        clean = item.strip()
        if clean:
            aliases.append(clean)
    return aliases


def _expand_aliases(value: str) -> list[str]:
    aliases = set(_split_aliases(value))
    for match in _PROPERTIES_RE.finditer(value):
        inner = match.group("inner").strip()
        if inner == "$all":
            continue
        aliases.update(_split_aliases(inner))
    return sorted(aliases)


def _expand_all(value: str) -> bool:
    return any(match.group("inner").strip() == "$all" for match in _PROPERTIES_RE.finditer(value))
