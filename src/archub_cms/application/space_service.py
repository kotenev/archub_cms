"""Application service for the spaces context (Confluence-style).

Manages knowledge spaces with settings, permissions, and metadata.
"""

from __future__ import annotations

__all__ = ["SpaceService", "get_archub_space_service"]

from typing import Any

from archub_cms.domain.spaces.repository import SpaceRepository
from archub_cms.domain.spaces.space import Space


class SpaceService:
    def __init__(self, *, repository: SpaceRepository | None = None) -> None:
        self._repo = repository

    def list_all(self) -> dict[str, Any]:
        if self._repo is None:
            return {"items": [], "total": 0}
        spaces = self._repo.list_all()
        return {
            "items": [space.as_dict() for space in spaces],
            "total": len(spaces),
        }

    def get(self, space_key: str) -> dict[str, Any] | None:
        if self._repo is None:
            return None
        space = self._repo.get(space_key)
        return space.as_dict() if space else None

    def upsert(self, space: Space) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("no repository configured")
        result = self._repo.upsert(space)
        return result.as_dict()

    def delete(self, space_key: str) -> bool:
        if self._repo is None:
            return False
        return self._repo.delete(space_key)

    def by_owner(self, owner: str) -> dict[str, Any]:
        if self._repo is None:
            return {"items": [], "total": 0}
        spaces = self._repo.find_by_owner(owner)
        return {
            "items": [space.as_dict() for space in spaces],
            "total": len(spaces),
        }


def get_archub_space_service(*, repository: SpaceRepository | None = None) -> SpaceService:
    return SpaceService(repository=repository)
