"""Modeling repository adapter.

Maps the legacy service's *hydrated* content-type/data-type/template reads to the
clean ``domain.modeling`` aggregates. Content-type hydration (merging composition
fields, resolving data types) is intricate and remains in ``cms.py``; this adapter
sources from those reads and translates, so the modeling context gets a proper
domain model and hexagonal port now while the raw SQL relocation is staged.
"""

from __future__ import annotations

__all__ = ["CmsModelingRepository"]

from archub_cms.domain.modeling.content_type import ContentTypeModel, DataType, Template
from archub_cms.domain.modeling.field import Field
from archub_cms.services.cms import (
    ArcHubCMSService,
    ContentDataType,
    ContentField,
    ContentTemplate,
    ContentType,
    get_archub_cms_service,
)


def _field(field: ContentField) -> Field:
    return Field(
        alias=field.alias,
        name=field.name,
        editor=field.editor,
        required=field.required,
        help_text=field.help_text,
        default=field.default,
        data_type_alias=field.data_type_alias,
        config=dict(field.config),
        validation=dict(field.validation),
    )


def _content_type(content_type: ContentType) -> ContentTypeModel:
    return ContentTypeModel(
        alias=content_type.alias,
        name=content_type.name,
        icon=content_type.icon,
        description=content_type.description,
        fields=tuple(_field(f) for f in content_type.fields),
        allowed_child_aliases=tuple(content_type.allowed_child_aliases),
        composition_aliases=tuple(content_type.composition_aliases),
        allow_at_root=content_type.allow_at_root,
        is_element=content_type.is_element,
        template=content_type.template,
        created_at=content_type.created_at,
        updated_at=content_type.updated_at,
    )


def _data_type(data_type: ContentDataType) -> DataType:
    return DataType(
        alias=data_type.alias,
        name=data_type.name,
        editor=data_type.editor,
        description=data_type.description,
        config=dict(data_type.config),
        validation=dict(data_type.validation),
    )


def _template(template: ContentTemplate) -> Template:
    return Template(
        alias=template.alias,
        name=template.name,
        view=template.view,
        description=template.description,
        allowed_content_type_aliases=tuple(template.allowed_content_type_aliases),
        config=dict(template.config),
    )


class CmsModelingRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def list_content_types(self) -> list[ContentTypeModel]:
        return [_content_type(ct) for ct in self._cms.list_content_types()]

    def get_content_type(self, alias: str) -> ContentTypeModel | None:
        found = self._cms.get_content_type(alias)
        return _content_type(found) if found is not None else None

    def list_data_types(self, *, limit: int = 200) -> list[DataType]:
        return [_data_type(dt) for dt in self._cms.list_data_types(limit=limit)]

    def get_data_type(self, alias: str) -> DataType | None:
        found = self._cms.get_data_type(alias)
        return _data_type(found) if found is not None else None

    def list_templates(self, *, limit: int = 200) -> list[Template]:
        return [_template(t) for t in self._cms.list_templates(limit=limit)]
