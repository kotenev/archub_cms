"""Blueprint repository adapter mapping legacy blueprint reads to the aggregate."""

from __future__ import annotations

__all__ = ["CmsBlueprintRepository"]

from archub_cms.domain.blueprints.blueprint import Blueprint
from archub_cms.services.cms import ArcHubCMSService, ContentBlueprint, get_archub_cms_service


def _blueprint(blueprint: ContentBlueprint) -> Blueprint:
    return Blueprint(
        blueprint_id=blueprint.blueprint_id,
        content_type_alias=blueprint.content_type_alias,
        name=blueprint.name,
        description=blueprint.description,
        payload=dict(blueprint.payload),
    )


class CmsBlueprintRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def list_blueprints(self, *, content_type_alias: str = "", limit: int = 100) -> list[Blueprint]:
        return [
            _blueprint(b)
            for b in self._cms.list_content_blueprints(
                content_type_alias=content_type_alias, limit=limit
            )
        ]

    def get(self, blueprint_id: str) -> Blueprint | None:
        found = self._cms.get_content_blueprint(blueprint_id)
        return _blueprint(found) if found is not None else None
