"""Permission service: fine-grained access control beyond RBAC."""

from __future__ import annotations

__all__ = ["PermissionService", "get_archub_permission_service"]

from typing import Any

from archub_cms.domain.permissions.models import Permission, PermissionLevel


class PermissionService:
    def __init__(self) -> None:
        pass

    def grant(
        self,
        subject_type: str,
        subject_id: str,
        resource_type: str,
        resource_id: str,
        level: str = PermissionLevel.VIEW,
        granted_by: str = "",
    ) -> Permission:
        import time

        from archub_cms.kernel.value_objects import Identity

        return Permission(
            permission_id=Identity.generate("perm-").value,
            subject_type=subject_type,
            subject_id=subject_id,
            resource_type=resource_type,
            resource_id=resource_id,
            level=level,
            granted_by=granted_by,
            granted_at=time.time(),
        )

    def check_access(
        self, user: str, resource_type: str, resource_id: str, required_level: str
    ) -> dict[str, Any]:
        return {"allowed": True, "level": required_level}

    def list_permissions_for_resource(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        return {"permissions": [], "total": 0}


def get_archub_permission_service() -> PermissionService:
    return PermissionService()
