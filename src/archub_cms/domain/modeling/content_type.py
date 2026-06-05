"""The content-modeling aggregates: ContentTypeModel, DataType, Template."""

from __future__ import annotations

__all__ = ["ContentTypeModel", "DataType", "Template"]

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from archub_cms.domain.modeling.field import ALIAS_RE, Field


@dataclass(frozen=True)
class DataType:
    """A reusable editor configuration bound to fields (Umbraco data type)."""

    alias: str
    name: str
    editor: str = "text"
    description: str = ""
    config: dict[str, Any] = dataclass_field(default_factory=dict)
    validation: dict[str, Any] = dataclass_field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "name": self.name,
            "editor": self.editor,
            "description": self.description,
            "config": dict(self.config),
            "validation": dict(self.validation),
        }


@dataclass(frozen=True)
class Template:
    """A render template a content type can be presented through."""

    alias: str
    name: str
    view: str = "archub_public.html"
    description: str = ""
    allowed_content_type_aliases: tuple[str, ...] = ()
    config: dict[str, Any] = dataclass_field(default_factory=dict)

    def allows(self, content_type_alias: str) -> bool:
        return (
            not self.allowed_content_type_aliases
            or content_type_alias in self.allowed_content_type_aliases
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "name": self.name,
            "view": self.view,
            "description": self.description,
            "allowed_content_type_aliases": list(self.allowed_content_type_aliases),
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class ContentTypeModel:
    """A document type: typed fields, compositions, allowed children, template."""

    alias: str
    name: str
    icon: str = ""
    description: str = ""
    fields: tuple[Field, ...] = ()
    allowed_child_aliases: tuple[str, ...] = ()
    composition_aliases: tuple[str, ...] = ()
    allow_at_root: bool = False
    is_element: bool = False
    template: str = "page"
    created_at: float = 0.0
    updated_at: float = 0.0

    def field(self, alias: str) -> Field | None:
        for item in self.fields:
            if item.alias == alias:
                return item
        return None

    @property
    def is_composed(self) -> bool:
        return bool(self.composition_aliases)

    def allows_child(self, alias: str) -> bool:
        return alias in self.allowed_child_aliases

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not ALIAS_RE.fullmatch(self.alias):
            errors.append(f"content type alias must match {ALIAS_RE.pattern}")
        if not self.name.strip():
            errors.append("content type name is required")
        for fld in self.fields:
            errors.extend(f"{self.alias}.{err}" for err in fld.validate())
        if self.is_element and self.allow_at_root:
            errors.append("element types cannot be allowed at root")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "fields": [fld.as_dict() for fld in self.fields],
            "field_aliases": [fld.alias for fld in self.fields],
            "allowed_child_aliases": list(self.allowed_child_aliases),
            "composition_aliases": list(self.composition_aliases),
            "allow_at_root": self.allow_at_root,
            "is_element": self.is_element,
            "is_composed": self.is_composed,
            "template": self.template,
            "updated_at": self.updated_at,
        }
