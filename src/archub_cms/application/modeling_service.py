"""Application service for the modeling context (DDD, CQRS-lite).

``ModelingQueryService`` reads schema via the :class:`ModelingRepository` and
returns domain models. ``ModelingCommandService`` runs schema changes — it
validates the intended ``ContentTypeModel`` against domain invariants *before*
delegating persistence to the legacy service, then publishes a domain event to
the kernel bus. Complements the older ``application/modeling.py`` facade with a
real domain layer.
"""

from __future__ import annotations

__all__ = [
    "ModelingCommandService",
    "ModelingQueryService",
    "get_archub_modeling_query_service",
]

from collections.abc import Iterable
from typing import Any

from archub_cms.domain.modeling.content_type import ContentTypeModel
from archub_cms.domain.modeling.field import Field
from archub_cms.domain.modeling.repository import ModelingRepository
from archub_cms.infrastructure.sqlite.modeling_repository import CmsModelingRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class ModelingQueryService:
    def __init__(self, repository: ModelingRepository) -> None:
        self._repo = repository

    def content_types(self) -> dict[str, Any]:
        items = self._repo.list_content_types()
        return {"items": [ct.as_dict() for ct in items], "total": len(items)}

    def content_type(self, alias: str) -> dict[str, Any] | None:
        found = self._repo.get_content_type(alias)
        return found.as_dict() if found is not None else None

    def data_types(self, *, limit: int = 200) -> dict[str, Any]:
        items = self._repo.list_data_types(limit=limit)
        return {"items": [dt.as_dict() for dt in items], "total": len(items)}

    def templates(self, *, limit: int = 200) -> dict[str, Any]:
        items = self._repo.list_templates(limit=limit)
        return {"items": [t.as_dict() for t in items], "total": len(items)}

    def report(self) -> dict[str, Any]:
        content_types = self._repo.list_content_types()
        data_types = self._repo.list_data_types()
        templates = self._repo.list_templates()
        return {
            "content_type_total": len(content_types),
            "data_type_total": len(data_types),
            "template_total": len(templates),
            "composed_content_types": sum(1 for ct in content_types if ct.is_composed),
            "element_types": sum(1 for ct in content_types if ct.is_element),
            "root_allowed_types": [ct.alias for ct in content_types if ct.allow_at_root],
        }


class ModelingCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: ModelingRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsModelingRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def upsert_content_type(
        self,
        *,
        alias: str,
        name: str,
        icon: str = "□",
        description: str = "",
        fields: Iterable[dict[str, Any]] = (),
        allowed_child_aliases: Iterable[str] = (),
        composition_aliases: Iterable[str] = (),
        allow_at_root: bool = False,
        is_element: bool = False,
        template: str = "page",
        actor: str,
    ) -> ContentTypeModel:
        domain_fields = tuple(
            Field(
                alias=str(f.get("alias") or ""),
                name=str(f.get("name") or ""),
                editor=str(f.get("editor") or "text"),
                required=bool(f.get("required")),
                data_type_alias=str(f.get("data_type_alias") or ""),
            )
            for f in fields
        )
        candidate = ContentTypeModel(
            alias=alias,
            name=name,
            icon=icon,
            description=description,
            fields=domain_fields,
            allowed_child_aliases=tuple(allowed_child_aliases),
            composition_aliases=tuple(composition_aliases),
            allow_at_root=allow_at_root,
            is_element=is_element,
            template=template,
        )
        errors = candidate.validate()
        if errors:
            raise ValueError("; ".join(errors))

        self._cms.upsert_content_type(
            alias=alias,
            name=name,
            icon=icon,
            description=description,
            fields=list(fields),
            allowed_child_aliases=list(allowed_child_aliases),
            composition_aliases=list(composition_aliases),
            allow_at_root=allow_at_root,
            is_element=is_element,
            template=template,
            updated_by=actor,
        )
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="content_model.type.upserted",
                aggregate_id=alias,
                actor=actor,
                metadata={
                    "is_element": is_element,
                    "composed": bool(candidate.composition_aliases),
                },
            )
        )
        stored = self._repo.get_content_type(alias)
        assert stored is not None
        return stored


def get_archub_modeling_query_service(
    *, cms: ArcHubCMSService | None = None, repository: ModelingRepository | None = None
) -> ModelingQueryService:
    return ModelingQueryService(repository or CmsModelingRepository(cms))
