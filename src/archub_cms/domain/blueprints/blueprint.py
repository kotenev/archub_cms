"""The ``Blueprint`` aggregate (a reusable content template)."""

from __future__ import annotations

__all__ = ["Blueprint"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Blueprint:
    """A pre-filled template payload for a content type."""

    blueprint_id: str
    content_type_alias: str
    name: str
    description: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def field_names(self) -> tuple[str, ...]:
        return tuple(sorted(self.payload))

    def merge_overrides(self, overrides: dict[str, Any] | None) -> dict[str, Any]:
        """The final payload when instantiated: template fields, then overrides."""
        return {**self.payload, **(overrides or {})}

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("blueprint name is required")
        if not self.content_type_alias.strip():
            errors.append("blueprint content_type_alias is required")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "blueprint_id": self.blueprint_id,
            "content_type_alias": self.content_type_alias,
            "name": self.name,
            "description": self.description,
            "field_names": list(self.field_names()),
        }
        if include_payload:
            data["payload"] = dict(self.payload)
        return data
