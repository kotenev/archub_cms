"""Custom field service: user-defined metadata on content."""

from __future__ import annotations

__all__ = ["CustomFieldService", "get_archub_custom_field_service"]

from typing import Any

from archub_cms.domain.custom_fields.models import CustomField, CustomFieldDefinition


class CustomFieldService:
    def __init__(self) -> None:
        pass

    def define_field(
        self,
        name: str,
        field_type: str,
        space_key: str = "",
        description: str = "",
        required: bool = False,
        options: tuple[str, ...] = (),
    ) -> CustomFieldDefinition:
        from archub_cms.kernel.value_objects import Identity

        return CustomFieldDefinition(
            field_id=Identity.generate("field-").value,
            name=name,
            field_type=field_type,
            space_key=space_key,
            description=description,
            required=required,
            options=options,
        )

    def set_field_value(
        self, definition: CustomFieldDefinition, node_id: str, value: str
    ) -> CustomField:
        return CustomField(
            field_id=definition.field_id,
            definition=definition,
            node_id=node_id,
            value=value,
        )

    def list_field_definitions(self, space_key: str = "") -> dict[str, Any]:
        return {"definitions": [], "total": 0}

    def get_field_values(self, node_id: str) -> dict[str, Any]:
        return {"fields": {}, "total": 0}


def get_archub_custom_field_service() -> CustomFieldService:
    return CustomFieldService()
