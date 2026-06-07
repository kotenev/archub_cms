"""Permission domain models."""

from __future__ import annotations

__all__ = ["Permission", "PermissionLevel", "PermissionScope"]

from dataclasses import dataclass
from typing import Any


class PermissionLevel:
    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"
    NONE = "none"


class PermissionScope:
    PAGE = "page"
    SPACE = "space"
    GLOBAL = "global"


@dataclass(frozen=True)
class Permission:
    permission_id: str
    subject_type: str
    subject_id: str
    resource_type: str
    resource_id: str
    level: str = PermissionLevel.VIEW
    scope: str = PermissionScope.PAGE
    granted_by: str = ""
    granted_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "level": self.level,
            "scope": self.scope,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
        }

    def implies(self, required_level: str) -> bool:
        hierarchy = {
            PermissionLevel.NONE: 0,
            PermissionLevel.VIEW: 1,
            PermissionLevel.EDIT: 2,
            PermissionLevel.ADMIN: 3,
        }
        return hierarchy.get(self.level, 0) >= hierarchy.get(required_level, 0)
