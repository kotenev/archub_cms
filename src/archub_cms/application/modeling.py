"""Content modeling application service for ArcHub CMS.

.. deprecated:: Superseded by the modeling bounded context
   (``archub_cms.application.modeling_service`` — ``ModelingQueryService`` /
   ``ModelingCommandService`` over ``domain.modeling``). This thin facade is kept
   for back-compat; prefer the new context for a domain model + invariants.
"""

from __future__ import annotations

__all__ = [
    "ModelingOperationResult",
    "ArcHubModelingService",
    "get_archub_modeling_service",
]

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from archub_cms.domain.events import ArcHubDomainEvent
from archub_cms.services.cms import ArcHubCMSService, ContentField, get_archub_cms_service


@dataclass(frozen=True)
class ModelingOperationResult:
    """Result envelope for schema-driven modeling use cases."""

    payload: dict[str, Any]
    events: tuple[ArcHubDomainEvent, ...] = ()
    status_code: int = 200

    def as_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        if not include_events:
            return self.payload
        return {
            **self.payload,
            "events": [event.as_dict() for event in self.events],
        }


class ArcHubModelingService:
    """Application boundary for data types, templates, document types, and blueprints."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def report(self) -> dict[str, Any]:
        return self._cms.content_model_report()

    def data_types(self, *, limit: int = 200) -> dict[str, Any]:
        items = self._cms.list_data_types(limit=limit)
        return {"items": [item.__dict__ for item in items], "total": len(items)}

    def templates(self, *, limit: int = 200) -> dict[str, Any]:
        items = self._cms.list_templates(limit=limit)
        return {"items": [item.__dict__ for item in items], "total": len(items)}

    def blueprints(self, *, content_type_alias: str = "", limit: int = 100) -> dict[str, Any]:
        items = self._cms.list_content_blueprints(
            content_type_alias=content_type_alias,
            limit=limit,
        )
        return {"items": [item.__dict__ for item in items], "total": len(items)}

    def upsert_data_type(
        self,
        *,
        alias: str,
        name: str,
        editor: str,
        description: str = "",
        config: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        actor: str,
    ) -> ModelingOperationResult:
        data_type = self._cms.upsert_data_type(
            alias=alias,
            name=name,
            editor=editor,
            description=description,
            config=config,
            validation=validation,
            updated_by=actor,
        )
        return ModelingOperationResult(
            payload=data_type.__dict__,
            events=(
                _model_event(
                    "content_model.data_type.upserted",
                    data_type.alias,
                    actor=actor,
                    metadata={"editor": data_type.editor},
                ),
            ),
        )

    def upsert_template(
        self,
        *,
        alias: str,
        name: str,
        view: str,
        description: str = "",
        allowed_content_type_aliases: Iterable[str] = (),
        config: dict[str, Any] | None = None,
        actor: str,
    ) -> ModelingOperationResult:
        template = self._cms.upsert_template(
            alias=alias,
            name=name,
            view=view,
            description=description,
            allowed_content_type_aliases=allowed_content_type_aliases,
            config=config,
            updated_by=actor,
        )
        return ModelingOperationResult(
            payload=template.__dict__,
            events=(
                _model_event(
                    "content_model.template.upserted",
                    template.alias,
                    actor=actor,
                    metadata={
                        "view": template.view,
                        "allowed_content_type_aliases": list(template.allowed_content_type_aliases),
                    },
                ),
            ),
        )

    def upsert_composition(
        self,
        *,
        alias: str,
        name: str,
        description: str = "",
        fields: Iterable[dict[str, Any] | ContentField] = (),
        actor: str,
    ) -> ModelingOperationResult:
        composition = self._cms.upsert_content_composition(
            alias=alias,
            name=name,
            description=description,
            fields=fields,
            updated_by=actor,
        )
        return ModelingOperationResult(
            payload=composition.__dict__,
            events=(
                _model_event(
                    "content_model.composition.upserted",
                    composition.alias,
                    actor=actor,
                    metadata={"fields": [field.alias for field in composition.fields]},
                ),
            ),
        )

    def upsert_content_type(
        self,
        *,
        alias: str,
        name: str,
        icon: str = "□",
        description: str = "",
        fields: Iterable[dict[str, Any] | ContentField] = (),
        allowed_child_aliases: Iterable[str] = (),
        composition_aliases: Iterable[str] = (),
        allow_at_root: bool = False,
        is_element: bool = False,
        template: str = "page",
        actor: str,
    ) -> ModelingOperationResult:
        content_type = self._cms.upsert_content_type(
            alias=alias,
            name=name,
            icon=icon,
            description=description,
            fields=fields,
            allowed_child_aliases=allowed_child_aliases,
            composition_aliases=composition_aliases,
            allow_at_root=allow_at_root,
            is_element=is_element,
            template=template,
            updated_by=actor,
        )
        return ModelingOperationResult(
            payload=content_type.__dict__,
            events=(
                _model_event(
                    "content_model.type.upserted",
                    content_type.alias,
                    actor=actor,
                    metadata={
                        "fields": [field.alias for field in content_type.fields],
                        "composition_aliases": list(content_type.composition_aliases),
                        "allowed_child_aliases": list(content_type.allowed_child_aliases),
                    },
                ),
            ),
        )

    def upsert_blueprint(
        self,
        *,
        content_type_alias: str,
        name: str,
        payload: dict[str, Any],
        description: str = "",
        actor: str,
        blueprint_id: str = "",
    ) -> ModelingOperationResult:
        blueprint = self._cms.upsert_content_blueprint(
            blueprint_id=blueprint_id,
            content_type_alias=content_type_alias,
            name=name,
            description=description,
            payload=payload,
            updated_by=actor,
        )
        return ModelingOperationResult(
            payload=blueprint.__dict__,
            events=(
                _model_event(
                    "content_model.blueprint.upserted",
                    blueprint.blueprint_id,
                    actor=actor,
                    metadata={
                        "content_type_alias": blueprint.content_type_alias,
                        "fields": sorted(blueprint.payload),
                    },
                ),
            ),
        )

    def delete_blueprint(self, blueprint_id: str, *, actor: str) -> ModelingOperationResult:
        deleted = self._cms.delete_content_blueprint(blueprint_id, deleted_by=actor)
        return ModelingOperationResult(
            payload={"ok": deleted, "blueprint_id": blueprint_id},
            events=(
                _model_event(
                    "content_model.blueprint.deleted",
                    blueprint_id,
                    actor=actor,
                    metadata={"deleted": deleted},
                ),
            ),
            status_code=200 if deleted else 404,
        )


def get_archub_modeling_service(cms: ArcHubCMSService | None = None) -> ArcHubModelingService:
    return ArcHubModelingService(cms=cms)


def _model_event(
    event_type: str,
    aggregate_id: str,
    *,
    actor: str,
    metadata: dict[str, Any] | None = None,
) -> ArcHubDomainEvent:
    return ArcHubDomainEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        actor=actor,
        metadata=metadata or {},
    )
