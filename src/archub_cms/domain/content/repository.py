"""Repository port for the content context (hexagonal boundary)."""

from __future__ import annotations

__all__ = ["ContentRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.content.node import ContentNode


@runtime_checkable
class ContentRepository(Protocol):
    """Read access to the content tree, returning domain aggregates.

    Implementations live in infrastructure. Writes remain, for now, in the
    legacy service; later phases move them behind command methods here.
    """

    def get(self, node_id: str) -> ContentNode | None: ...

    def get_by_route(self, route_path: str) -> ContentNode | None: ...

    def list_tree(self, *, include_trashed: bool = False) -> list[ContentNode]: ...

    def children(self, parent_id: str | None) -> list[ContentNode]: ...

    def slug_exists(
        self, parent_id: str | None, slug: str, *, exclude_id: str | None = None
    ) -> bool: ...
