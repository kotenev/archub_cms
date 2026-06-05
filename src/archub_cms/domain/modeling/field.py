"""The ``Field`` value object for content-type schemas."""

from __future__ import annotations

__all__ = ["Field"]

import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

ALIAS_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class Field:
    """A typed field on a content type (editor + optional data-type binding)."""

    alias: str
    name: str
    editor: str = "text"
    required: bool = False
    help_text: str = ""
    default: str = ""
    data_type_alias: str = ""
    config: dict[str, Any] = dataclass_field(default_factory=dict)
    validation: dict[str, Any] = dataclass_field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not ALIAS_RE.fullmatch(self.alias):
            errors.append(f"field alias must match {ALIAS_RE.pattern}")
        if not self.name.strip():
            errors.append("field name is required")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "name": self.name,
            "editor": self.editor,
            "required": self.required,
            "help_text": self.help_text,
            "default": self.default,
            "data_type_alias": self.data_type_alias,
            "config": dict(self.config),
            "validation": dict(self.validation),
        }
