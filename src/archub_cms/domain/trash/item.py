"""The ``TrashedItem`` read model (a node in the recycle bin)."""

from __future__ import annotations

__all__ = ["TrashedItem"]

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrashedItem:
    node_id: str
    name: str
    content_type_alias: str = ""
    original_route_path: str = ""
    slug: str = ""
    original_parent_id: str | None = None
    original_status: str = ""
    trashed_at: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TrashedItem:
        return cls(
            node_id=str(payload.get("node_id") or ""),
            name=str(payload.get("name") or ""),
            content_type_alias=str(payload.get("content_type_alias") or ""),
            original_route_path=str(payload.get("route_path") or ""),
            slug=str(payload.get("slug") or ""),
            original_parent_id=payload.get("original_parent_id"),
            original_status=str(payload.get("original_status") or ""),
            trashed_at=float(payload.get("trashed_at") or 0.0),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "content_type_alias": self.content_type_alias,
            "original_route_path": self.original_route_path,
            "slug": self.slug,
            "original_parent_id": self.original_parent_id,
            "original_status": self.original_status,
            "trashed_at": self.trashed_at,
        }
