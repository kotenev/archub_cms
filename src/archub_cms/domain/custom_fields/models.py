"""Custom field domain models."""

from __future__ import annotations

__all__ = ["CustomField", "CustomFieldDefinition", "CustomFieldType"]

from dataclasses import dataclass
from typing import Any


class CustomFieldType:
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    URL = "url"
    USER = "user"


@dataclass(frozen=True)
class CustomFieldDefinition:
    field_id: str
    name: str
    field_type: str
    description: str = ""
    required: bool = False
    options: tuple[str, ...] = ()
    default_value: str = ""
    space_key: str = ""
    sort_order: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "name": self.name,
            "field_type": self.field_type,
            "description": self.description,
            "required": self.required,
            "options": list(self.options),
            "default_value": self.default_value,
            "space_key": self.space_key,
            "sort_order": self.sort_order,
        }


@dataclass(frozen=True)
class CustomField:
    field_id: str
    definition: CustomFieldDefinition
    node_id: str
    value: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "definition": self.definition.as_dict(),
            "node_id": self.node_id,
            "value": self.value,
        }
