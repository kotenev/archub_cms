"""REST/API and HTML routes for the ITSM Service Desk plugin.

These endpoints expose the loaded :class:`ServiceDesk` over HTTP under
``/api/platform/itsm``. They follow the same conventions as the rest of the platform
router (plain dict bodies, ``HTTPException`` for errors, the shared plugin host), and
return ``503`` when the ITSM plugin is disabled so callers get a clear signal rather
than a generic 500.
"""

from __future__ import annotations

__all__ = ["itsm_router", "itsm_web_router"]

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from archub_cms.extensibility.example_plugins.itsm.bpmn import to_bpmn_xml, to_mermaid
from archub_cms.extensibility.example_plugins.itsm.rbac import (
    ITSMPermission,
    actor_role_for_groups,
    has_itsm_permission,
    itil_role_report,
    permissions_for_groups,
    roles_for_groups,
)
from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    RequestType,
)
from archub_cms.extensibility.example_plugins.itsm.service_desk import (
    RequestNotFoundError,
    ServiceDesk,
)
from archub_cms.extensibility.example_plugins.itsm.workflow import WorkflowError, WorkflowScheme
from archub_cms.extensibility.host import get_plugin_host
from archub_cms.web._common import current_user, templates

itsm_router = APIRouter(prefix="/api/platform/itsm", tags=["itsm"])
itsm_web_router = APIRouter(tags=["itsm"])

_PLUGIN_ID = "archub.itsm.service_desk"
_TEMPLATES = templates()


@dataclass(frozen=True)
class ITSMIdentity:
    username: str
    is_admin: bool
    groups: tuple[str, ...]
    actor_role: str
    permissions: tuple[ITSMPermission, ...]

    @property
    def roles(self) -> tuple[dict[str, object], ...]:
        return tuple(role.as_dict() for role in roles_for_groups(self.groups))

    def can(self, permission: ITSMPermission) -> bool:
        return has_itsm_permission(self.groups, permission, is_admin=self.is_admin)

    def as_dict(self) -> dict[str, Any]:
        return {
            "authenticated": True,
            "username": self.username,
            "is_admin": self.is_admin,
            "groups": list(self.groups),
            "actor_role": self.actor_role,
            "permissions": [permission.value for permission in self.permissions],
            "roles": list(self.roles),
        }


def _service_desk() -> ServiceDesk:
    host = get_plugin_host()
    plugin = host.plugin_instance(_PLUGIN_ID)
    desk = getattr(plugin, "desk", None) if plugin is not None else None
    if desk is None:
        raise HTTPException(
            status_code=503,
            detail="ITSM Service Desk plugin is not enabled",
        )
    assert isinstance(desk, ServiceDesk)
    return desk


def _identity_from_request(request: Request) -> ITSMIdentity:
    host = get_plugin_host()
    identity = host.authenticate(request) or current_user(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="ITSM authentication required")
    username = str(getattr(identity, "username", "") or "").strip()
    is_admin = bool(getattr(identity, "is_admin", False))
    groups = tuple(str(group).strip() for group in getattr(identity, "groups", ()) if group)
    permissions = permissions_for_groups(groups, is_admin=is_admin)
    actor_role = actor_role_for_groups(groups, is_admin=is_admin)
    return ITSMIdentity(
        username=username,
        is_admin=is_admin,
        groups=groups,
        actor_role=actor_role,
        permissions=permissions,
    )


def _require(permission: ITSMPermission):
    def dependency(request: Request) -> ITSMIdentity:
        identity = _identity_from_request(request)
        if not identity.can(permission):
            raise HTTPException(
                status_code=403,
                detail=f"ITSM permission required: {permission.value}",
            )
        return identity

    return dependency


def _ensure_permission(identity: ITSMIdentity, permission: ITSMPermission) -> None:
    if not identity.can(permission):
        raise HTTPException(
            status_code=403,
            detail=f"ITSM permission required: {permission.value}",
        )


def _workflow_actor_role(identity: ITSMIdentity, requested: Any = "") -> str:
    clean_requested = str(requested or "").strip().lower()
    if identity.is_admin and clean_requested:
        return clean_requested
    return identity.actor_role


_ITSM_READ = Depends(_require(ITSMPermission.READ))
_ITSM_CREATE_REQUEST = Depends(_require(ITSMPermission.CREATE_REQUEST))
_ITSM_TRANSITION = Depends(_require(ITSMPermission.TRANSITION))
_ITSM_ASSIGN = Depends(_require(ITSMPermission.ASSIGN))


def _scheme(desk: ServiceDesk, key: str) -> WorkflowScheme:
    scheme = desk.schemes.get(key)
    if scheme is None:
        available = ", ".join(sorted(desk.schemes)) or "(none)"
        raise HTTPException(
            status_code=404,
            detail=f"unknown workflow scheme {key!r}; available: {available}",
        )
    return scheme


def _parse_request_type(value: Any) -> RequestType:
    try:
        return RequestType(str(value))
    except ValueError as exc:
        allowed = ", ".join(t.value for t in RequestType)
        raise HTTPException(
            status_code=422,
            detail=f"unknown request type {value!r}; allowed: {allowed}",
        ) from exc


def _parse_priority(value: Any, *, default: Priority = Priority.MEDIUM) -> Priority:
    if value in (None, ""):
        return default
    try:
        return Priority(str(value))
    except ValueError as exc:
        allowed = ", ".join(p.value for p in Priority)
        raise HTTPException(
            status_code=422,
            detail=f"unknown priority {value!r}; allowed: {allowed}",
        ) from exc


def _cloud_from(payload: dict[str, Any]) -> CloudResource | None:
    cloud = payload.get("cloud")
    if not isinstance(cloud, dict):
        return None
    return CloudResource(
        provider=str(cloud.get("provider") or ""),
        service=str(cloud.get("service") or ""),
        region=str(cloud.get("region") or ""),
        resource_id=str(cloud.get("resource_id") or cloud.get("resource") or ""),
    )


# -- schemes (workflow definitions + BPMN visualization) ----------------------


@itsm_router.get("/schemes")
def list_schemes(
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    desk = _service_desk()
    schemes = [scheme.as_dict() for scheme in desk.schemes.values()]
    return {"schemes": schemes, "total": len(schemes)}


@itsm_router.get("/schemes/{key}")
def scheme_detail(
    key: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    desk = _service_desk()
    return _scheme(desk, key).as_dict()


@itsm_router.get("/schemes/{key}/bpmn")
def scheme_bpmn(
    key: str,
    format: str = Query(default="xml"),
    _identity: ITSMIdentity = _ITSM_READ,
) -> Any:
    """Visualize a workflow scheme as BPMN 2.0 XML (default) or a Mermaid diagram."""

    desk = _service_desk()
    scheme = _scheme(desk, key)
    if format.lower() == "mermaid":
        return {"key": key, "format": "mermaid", "diagram": to_mermaid(scheme)}
    return Response(content=to_bpmn_xml(scheme), media_type="application/xml")


# -- requests -----------------------------------------------------------------


@itsm_router.get("/requests")
def list_requests(
    type: str = Query(default=""),
    status: str = Query(default=""),
    assignee: str = Query(default=""),
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    desk = _service_desk()
    request_type = _parse_request_type(type) if type else None
    items = desk.list_requests(
        type=request_type,
        status_id=status,
        assignee=assignee or None,
    )
    return {"requests": [item.as_dict() for item in items], "total": len(items)}


@itsm_router.post("/requests", status_code=201)
def create_request(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    identity: ITSMIdentity = _ITSM_CREATE_REQUEST,
) -> dict[str, Any]:
    desk = _service_desk()
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise HTTPException(status_code=422, detail="summary is required")
    request_type = _parse_request_type(payload.get("type") or "incident")
    if request_type is RequestType.CHANGE:
        _ensure_permission(identity, ITSMPermission.CREATE_CHANGE)
    priority = _parse_priority(payload.get("priority"))
    try:
        request = desk.create_request(
            type=request_type,
            summary=summary,
            description=str(payload.get("description") or ""),
            priority=priority,
            reporter=str(payload.get("reporter") or identity.username),
            cloud=_cloud_from(payload),
            scheme_key=str(payload.get("scheme_key") or ""),
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"unknown workflow scheme: {exc}") from exc
    return request.as_dict()


@itsm_router.get("/requests/{key}")
def get_request(
    key: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    desk = _service_desk()
    try:
        return desk.get(key).as_dict()
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@itsm_router.get("/requests/{key}/transitions")
def request_transitions(
    key: str,
    actor_role: str = Query(default=""),
    identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    desk = _service_desk()
    try:
        transitions = desk.available_transitions(
            key, actor_role=_workflow_actor_role(identity, actor_role)
        )
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"key": key, "transitions": list(transitions), "total": len(transitions)}


@itsm_router.post("/requests/{key}/transitions")
def apply_transition(
    key: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    identity: ITSMIdentity = _ITSM_TRANSITION,
) -> dict[str, Any]:
    desk = _service_desk()
    transition_id = str(payload.get("transition") or "").strip()
    if not transition_id:
        raise HTTPException(status_code=422, detail="transition is required")
    if transition_id == "approve" or bool(payload.get("approved")):
        _ensure_permission(identity, ITSMPermission.APPROVE)
    try:
        request = desk.transition(
            key,
            transition_id,
            actor=str(payload.get("actor") or identity.username),
            actor_role=_workflow_actor_role(identity, payload.get("actor_role")),
            resolution=str(payload.get("resolution") or ""),
            approved=bool(payload.get("approved")),
        )
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        # Illegal transition or unmet condition: a conflict with current state.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return request.as_dict()


@itsm_router.post("/requests/{key}/assign")
def assign_request(
    key: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    identity: ITSMIdentity = _ITSM_ASSIGN,
) -> dict[str, Any]:
    desk = _service_desk()
    assignee = str(payload.get("assignee") or "").strip()
    if not assignee:
        raise HTTPException(status_code=422, detail="assignee is required")
    try:
        request = desk.assign(key, assignee, actor=str(payload.get("actor") or identity.username))
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return request.as_dict()


# -- queue dashboard ----------------------------------------------------------


@itsm_router.get("/queue")
def queue_summary(
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    return _service_desk().queue_summary()


# -- RBAC + HTML dashboard ----------------------------------------------------


@itsm_router.get("/rbac/roles")
def rbac_roles(
    request: Request,
    identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    report = itil_role_report()
    return {
        **report,
        "current_user": identity.as_dict(),
        "login_headers": {
            "authorization": "Bearer demo-itsm-agent-token",
            "x_archub_groups": "itil:service_desk_agent",
        },
        "links": {
            "dashboard": str(request.url_for("itsm_dashboard")),
            "queue": "/api/platform/itsm/queue",
        },
    }


@itsm_web_router.get("/admin/itsm", response_class=HTMLResponse, name="itsm_dashboard")
def itsm_dashboard(
    request: Request,
    identity: ITSMIdentity = _ITSM_READ,
) -> HTMLResponse:
    desk = _service_desk()
    queue = desk.queue_summary()
    requests = [item.as_dict() for item in desk.list_requests()]
    schemes = [scheme.as_dict() for scheme in desk.schemes.values()]
    return _TEMPLATES.TemplateResponse(
        request,
        "archub_itsm_admin.html",
        {
            "title": "ArcHub ITSM",
            "current_user": identity.as_dict(),
            "queue": queue,
            "requests": requests,
            "schemes": schemes,
            "rbac": itil_role_report(),
            "can_create": identity.can(ITSMPermission.CREATE_REQUEST),
            "can_assign": identity.can(ITSMPermission.ASSIGN),
            "can_approve": identity.can(ITSMPermission.APPROVE),
        },
    )
