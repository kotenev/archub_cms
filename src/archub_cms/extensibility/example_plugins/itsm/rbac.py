"""ITIL-aligned RBAC roles for the ITSM Service Desk plugin."""

from __future__ import annotations

__all__ = [
    "ITILRole",
    "ITSMPermission",
    "actor_role_for_groups",
    "has_itsm_permission",
    "itil_role_report",
    "permissions_for_groups",
    "roles_for_groups",
]

from dataclasses import dataclass
from enum import StrEnum


class ITSMPermission(StrEnum):
    """Coarse-grained permissions enforced at the ITSM web/API boundary."""

    READ = "itsm:read"
    CREATE_REQUEST = "itsm:request:create"
    CREATE_CHANGE = "itsm:change:create"
    TRANSITION = "itsm:request:transition"
    ASSIGN = "itsm:request:assign"
    APPROVE = "itsm:approval"
    MANAGE = "itsm:manage"
    ADMIN = "itsm:admin"


@dataclass(frozen=True)
class ITILRole:
    """A platform role mapped to an ITIL practice and workflow actor role."""

    role_id: str
    name: str
    practice: str
    actor_role: str
    permissions: tuple[ITSMPermission, ...]
    aliases: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "practice": self.practice,
            "actor_role": self.actor_role,
            "permissions": [permission.value for permission in self.permissions],
            "groups": sorted(_aliases_for_role(self)),
        }


_ALL_PERMISSIONS = tuple(ITSMPermission)

_ROLES: tuple[ITILRole, ...] = (
    ITILRole(
        "itil:requester",
        "Requester",
        "Service request management",
        "customer",
        (ITSMPermission.READ, ITSMPermission.CREATE_REQUEST),
        aliases=("requester", "customer", "user"),
    ),
    ITILRole(
        "itil:service_desk_agent",
        "Service Desk Agent",
        "Service desk",
        "agent",
        (
            ITSMPermission.READ,
            ITSMPermission.CREATE_REQUEST,
            ITSMPermission.TRANSITION,
            ITSMPermission.ASSIGN,
        ),
        aliases=("service_desk_agent", "service-desk-agent", "agent"),
    ),
    ITILRole(
        "itil:incident_manager",
        "Incident Manager",
        "Incident management",
        "agent",
        (
            ITSMPermission.READ,
            ITSMPermission.CREATE_REQUEST,
            ITSMPermission.TRANSITION,
            ITSMPermission.ASSIGN,
            ITSMPermission.MANAGE,
        ),
        aliases=("incident_manager", "incident-manager"),
    ),
    ITILRole(
        "itil:problem_manager",
        "Problem Manager",
        "Problem management",
        "agent",
        (
            ITSMPermission.READ,
            ITSMPermission.CREATE_REQUEST,
            ITSMPermission.TRANSITION,
            ITSMPermission.ASSIGN,
            ITSMPermission.MANAGE,
        ),
        aliases=("problem_manager", "problem-manager"),
    ),
    ITILRole(
        "itil:service_request_fulfillment",
        "Service Request Fulfillment",
        "Service request management",
        "agent",
        (
            ITSMPermission.READ,
            ITSMPermission.CREATE_REQUEST,
            ITSMPermission.TRANSITION,
            ITSMPermission.ASSIGN,
        ),
        aliases=("service_request_fulfillment", "fulfillment"),
    ),
    ITILRole(
        "itil:change_manager",
        "Change Manager",
        "Change enablement",
        "manager",
        (
            ITSMPermission.READ,
            ITSMPermission.CREATE_REQUEST,
            ITSMPermission.CREATE_CHANGE,
            ITSMPermission.TRANSITION,
            ITSMPermission.ASSIGN,
            ITSMPermission.APPROVE,
            ITSMPermission.MANAGE,
        ),
        aliases=("change_manager", "change-manager", "manager"),
    ),
    ITILRole(
        "itil:cab_member",
        "CAB Member",
        "Change enablement",
        "manager",
        (ITSMPermission.READ, ITSMPermission.APPROVE),
        aliases=("cab_member", "cab-member", "cab"),
    ),
    ITILRole(
        "itil:release_manager",
        "Release Manager",
        "Release management",
        "manager",
        (
            ITSMPermission.READ,
            ITSMPermission.CREATE_CHANGE,
            ITSMPermission.TRANSITION,
            ITSMPermission.APPROVE,
            ITSMPermission.MANAGE,
        ),
        aliases=("release_manager", "release-manager"),
    ),
    ITILRole(
        "itil:service_owner",
        "Service Owner",
        "Service level management",
        "manager",
        (ITSMPermission.READ, ITSMPermission.APPROVE, ITSMPermission.MANAGE),
        aliases=("service_owner", "service-owner"),
    ),
    ITILRole(
        "itil:knowledge_manager",
        "Knowledge Manager",
        "Knowledge management",
        "viewer",
        (ITSMPermission.READ,),
        aliases=("knowledge_manager", "knowledge-manager"),
    ),
    ITILRole(
        "itil:auditor",
        "ITSM Auditor",
        "Measurement and reporting",
        "viewer",
        (ITSMPermission.READ,),
        aliases=("auditor", "itsm_auditor", "itsm-auditor"),
    ),
    ITILRole(
        "itil:itsm_admin",
        "ITSM Administrator",
        "ITSM administration",
        "admin",
        _ALL_PERMISSIONS,
        aliases=("itsm_admin", "itsm-admin", "admin"),
    ),
)


def _normalize_group(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _aliases_for_role(role: ITILRole) -> set[str]:
    base = {_normalize_group(role.role_id)}
    short = role.role_id.removeprefix("itil:")
    base.update(
        {
            short,
            short.replace("_", "-"),
            f"role:{role.role_id}",
            f"role:{short}",
        }
    )
    base.update(_normalize_group(alias) for alias in role.aliases)
    base.update(f"role:{_normalize_group(alias)}" for alias in role.aliases)
    return base


_ALIASES: dict[str, ITILRole] = {
    alias: role for role in _ROLES for alias in _aliases_for_role(role)
}


def roles_for_groups(groups: object) -> tuple[ITILRole, ...]:
    """Resolve ITIL roles from platform identity groups/header-auth groups."""

    if not isinstance(groups, (list, tuple, set, frozenset)):
        return ()
    resolved: dict[str, ITILRole] = {}
    for group in groups:
        role = _ALIASES.get(_normalize_group(str(group)))
        if role is not None:
            resolved[role.role_id] = role
    return tuple(resolved[key] for key in sorted(resolved))


def permissions_for_groups(groups: object, *, is_admin: bool = False) -> tuple[ITSMPermission, ...]:
    if is_admin:
        return _ALL_PERMISSIONS
    permissions: set[ITSMPermission] = set()
    for role in roles_for_groups(groups):
        permissions.update(role.permissions)
        if ITSMPermission.ADMIN in role.permissions:
            permissions.update(_ALL_PERMISSIONS)
    return tuple(permission for permission in _ALL_PERMISSIONS if permission in permissions)


def has_itsm_permission(
    groups: object, permission: ITSMPermission | str, *, is_admin: bool = False
) -> bool:
    requested = permission if isinstance(permission, ITSMPermission) else ITSMPermission(permission)
    permissions = permissions_for_groups(groups, is_admin=is_admin)
    return ITSMPermission.ADMIN in permissions or requested in permissions


def actor_role_for_groups(groups: object, *, is_admin: bool = False) -> str:
    """Return the workflow actor_role passed into ITSM workflow conditions."""

    if is_admin:
        return "admin"
    priorities = {"admin": 4, "manager": 3, "agent": 2, "customer": 1, "viewer": 0}
    best = "viewer"
    for role in roles_for_groups(groups):
        if priorities.get(role.actor_role, -1) > priorities.get(best, -1):
            best = role.actor_role
    return best


def itil_role_report() -> dict[str, object]:
    return {
        "roles": [role.as_dict() for role in _ROLES],
        "permissions": [permission.value for permission in _ALL_PERMISSIONS],
    }
