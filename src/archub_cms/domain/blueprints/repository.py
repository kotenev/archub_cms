"""Repository port for the blueprints context."""

from __future__ import annotations

__all__ = ["BlueprintRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.blueprints.blueprint import Blueprint


@runtime_checkable
class BlueprintRepository(Protocol):
    def list_blueprints(
        self, *, content_type_alias: str = "", limit: int = 100
    ) -> list[Blueprint]: ...

    def get(self, blueprint_id: str) -> Blueprint | None: ...
