"""The ``PermissionRule`` aggregate (RBAC grant)."""

from __future__ import annotations

__all__ = ["PERMISSION_ACTIONS", "PermissionRule"]

from dataclasses import dataclass
from typing import Any

PERMISSION_ACTIONS = (
    "browse",
    "create",
    "update",
    "publish",
    "delete",
    "workflow",
    "model",
    "media",
    "settings",
    "admin",
)


@dataclass(frozen=True)
class PermissionRule:
    """A subject granted a set of actions over an optional node scope."""

    rule_id: str
    subject: str
    actions: tuple[str, ...]
    scope_node_id: str = ""
    include_descendants: bool = True
    note: str = ""

    @property
    def is_global(self) -> bool:
        return not self.scope_node_id.strip()

    @property
    def is_admin(self) -> bool:
        return "admin" in self.actions

    def grants(self, action: str) -> bool:
        """Whether this rule grants ``action`` (admin grants everything)."""
        return self.is_admin or action in self.actions

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.subject.strip():
            errors.append("permission subject is required")
        if not self.actions:
            errors.append("at least one action is required")
        unknown = [a for a in self.actions if a not in PERMISSION_ACTIONS]
        if unknown:
            errors.append(f"unknown actions: {', '.join(unknown)}")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "subject": self.subject,
            "actions": list(self.actions),
            "scope_node_id": self.scope_node_id,
            "is_global": self.is_global,
            "include_descendants": self.include_descendants,
            "note": self.note,
        }
