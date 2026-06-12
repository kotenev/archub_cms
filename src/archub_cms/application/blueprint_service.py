"""Application service for the blueprints/templates context.

``BlueprintQueryService`` lists/gets templates. ``BlueprintCommandService``
creates templates and *instantiates* content from them (merging overrides over
the template payload), delegating persistence to the legacy service and emitting
domain events.
"""

from __future__ import annotations

__all__ = [
    "BlueprintCommandService",
    "BlueprintNotFoundError",
    "BlueprintQueryService",
    "get_archub_blueprint_query_service",
]

from typing import Any

from archub_cms.domain.blueprints.blueprint import Blueprint
from archub_cms.domain.blueprints.repository import BlueprintRepository
from archub_cms.infrastructure.sqlite.blueprint_repository import CmsBlueprintRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class BlueprintNotFoundError(LookupError):
    """Raised when instantiating from a blueprint id that does not exist."""


class BlueprintQueryService:
    def __init__(self, repository: BlueprintRepository) -> None:
        self._repo = repository

    def blueprints(self, *, content_type_alias: str = "", limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_blueprints(content_type_alias=content_type_alias, limit=limit)
        return {"items": [b.as_dict(include_payload=False) for b in items], "total": len(items)}

    def blueprint(self, blueprint_id: str) -> dict[str, Any] | None:
        found = self._repo.get(blueprint_id)
        return found.as_dict() if found is not None else None


class BlueprintCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: BlueprintRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsBlueprintRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def create_blueprint(
        self,
        *,
        content_type_alias: str,
        name: str,
        payload: dict[str, Any],
        description: str = "",
        actor: str,
        blueprint_id: str = "",
    ) -> Blueprint:
        candidate = Blueprint(
            blueprint_id=blueprint_id,
            content_type_alias=content_type_alias,
            name=name,
            description=description,
            payload=payload,
        )
        errors = candidate.validate()
        if errors:
            raise ValueError("; ".join(errors))

        stored = self._cms.upsert_content_blueprint(
            blueprint_id=blueprint_id,
            content_type_alias=content_type_alias,
            name=name,
            description=description,
            payload=payload,
            updated_by=actor,
        )
        self._bus.publish(
            ArcHubDomainEvent(
                "blueprint.upserted",
                stored.blueprint_id,
                actor,
                {"content_type": content_type_alias},
            )
        )
        return Blueprint(
            blueprint_id=stored.blueprint_id,
            content_type_alias=stored.content_type_alias,
            name=stored.name,
            description=stored.description,
            payload=dict(stored.payload),
        )

    def instantiate(
        self,
        blueprint_id: str,
        *,
        parent_id: str = "root",
        name: str,
        overrides: dict[str, Any] | None = None,
        actor: str,
    ) -> dict[str, Any]:
        blueprint = self._repo.get(blueprint_id)
        if blueprint is None:
            raise BlueprintNotFoundError(blueprint_id)
        node = self._cms.create_node_from_blueprint(
            blueprint_id=blueprint_id,
            parent_id=parent_id,
            name=name,
            payload_overrides=blueprint.merge_overrides(overrides),
            created_by=actor,
        )
        self._bus.publish(
            ArcHubDomainEvent(
                "content.instantiated_from_blueprint",
                node.node_id,
                actor,
                {"blueprint_id": blueprint_id, "route_path": node.route_path},
            )
        )
        return {
            "node_id": node.node_id,
            "route_path": node.route_path,
            "content_type_alias": node.content_type_alias,
            "blueprint_id": blueprint_id,
        }


def get_archub_blueprint_query_service(
    *, cms: ArcHubCMSService | None = None, repository: BlueprintRepository | None = None
) -> BlueprintQueryService:
    return BlueprintQueryService(repository or CmsBlueprintRepository(cms))
