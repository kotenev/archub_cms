"""REST/API and HTML routes for the ITSM Service Desk plugin.

These endpoints expose the loaded :class:`ServiceDesk` over HTTP under
``/api/platform/itsm``. They follow the same conventions as the rest of the platform
router (plain dict bodies, ``HTTPException`` for errors, the shared plugin host), and
return ``503`` when the ITSM plugin is disabled so callers get a clear signal rather
than a generic 500.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from archub_cms.extensibility.example_plugins.itsm.bpmn import to_bpmn_xml, to_mermaid
from archub_cms.extensibility.example_plugins.itsm.catalog import ServiceCatalogError
from archub_cms.extensibility.example_plugins.itsm.cmdb import CmdbError
from archub_cms.extensibility.example_plugins.itsm.itsm_service import (
    ItsmService,
    SchemeValidationError,
)
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
from archub_cms.extensibility.example_plugins.itsm.sla import SlaError
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
_ITSM_MANAGE = Depends(_require(ITSMPermission.MANAGE))
_ITSM_ADMIN = Depends(_require(ITSMPermission.ADMIN))


def _itsm_service() -> ItsmService:
    host = get_plugin_host()
    plugin = host.plugin_instance(_PLUGIN_ID)
    service = getattr(plugin, "itsm", None) if plugin is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="ITSM Service Desk plugin is not enabled")
    assert isinstance(service, ItsmService)
    return service


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


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
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise HTTPException(status_code=422, detail="summary is required")
    request_type = _parse_request_type(payload.get("type") or "incident")
    if request_type is RequestType.CHANGE:
        _ensure_permission(identity, ITSMPermission.CREATE_CHANGE)
    priority = _parse_priority(payload.get("priority"))
    # Route through the ITSM facade so a requested service's SLA is applied and the
    # affected configuration items are recorded for impact analysis.
    itsm = _itsm_service()
    ci_ids = tuple(str(c) for c in payload.get("ci_ids", ()) if str(c))
    try:
        request = itsm.log_request(
            type=request_type,
            summary=summary,
            description=str(payload.get("description") or ""),
            priority=priority,
            reporter=str(payload.get("reporter") or identity.username),
            cloud=_cloud_from(payload),
            scheme_key=str(payload.get("scheme_key") or ""),
            service_id=str(payload.get("service_id") or ""),
            sla_id=str(payload.get("sla_id") or ""),
            ci_ids=ci_ids,
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


@itsm_router.get("/requests/{key}/impact")
def request_impact(
    key: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    try:
        return _itsm_service().request_impact(key)
    except RequestNotFoundError as exc:
        raise _not_found(exc) from exc


@itsm_router.get("/report")
def itsm_report(
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    return _itsm_service().report()


# -- service catalog ----------------------------------------------------------


@itsm_router.get("/catalog")
def list_catalog(
    category: str = Query(default=""),
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    services = _itsm_service().catalog.list(category=category)
    return {"services": [s.as_dict() for s in services], "total": len(services)}


@itsm_router.post("/catalog", status_code=201)
def create_catalog_service(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    try:
        service = _itsm_service().catalog.create(**_catalog_fields(payload))
    except ServiceCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return service.as_dict()


@itsm_router.get("/catalog/{service_id}")
def get_catalog_service(
    service_id: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    try:
        return _itsm_service().catalog.get(service_id).as_dict()
    except ServiceCatalogError as exc:
        raise _not_found(exc) from exc


@itsm_router.put("/catalog/{service_id}")
def update_catalog_service(
    service_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    try:
        return _itsm_service().catalog.update(service_id, **_catalog_fields(payload)).as_dict()
    except ServiceCatalogError as exc:
        raise _not_found(exc) from exc


@itsm_router.delete("/catalog/{service_id}")
def delete_catalog_service(
    service_id: str,
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    return {"deleted": _itsm_service().catalog.delete(service_id)}


# -- SLA definitions ----------------------------------------------------------


@itsm_router.get("/sla")
def list_sla(
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    definitions = _itsm_service().sla.list()
    return {"sla": [d.as_dict() for d in definitions], "total": len(definitions)}


@itsm_router.post("/sla", status_code=201)
def create_sla(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    try:
        definition = _itsm_service().sla.create(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            description=str(payload.get("description") or ""),
            targets=payload.get("targets"),
        )
    except SlaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return definition.as_dict()


@itsm_router.get("/sla/{sla_id}")
def get_sla(
    sla_id: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    try:
        return _itsm_service().sla.get(sla_id).as_dict()
    except SlaError as exc:
        raise _not_found(exc) from exc


@itsm_router.put("/sla/{sla_id}")
def update_sla(
    sla_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    try:
        return (
            _itsm_service()
            .sla.update(
                sla_id,
                name=payload.get("name"),
                description=payload.get("description"),
                targets=payload.get("targets"),
            )
            .as_dict()
        )
    except SlaError as exc:
        raise _not_found(exc) from exc


@itsm_router.delete("/sla/{sla_id}")
def delete_sla(
    sla_id: str,
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    return {"deleted": _itsm_service().sla.delete(sla_id)}


# -- CMDB (configuration items + relationships + impact) ----------------------


@itsm_router.get("/cmdb/items")
def list_cmdb_items(
    type: str = Query(default=""),
    service_id: str = Query(default=""),
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    items = _itsm_service().cmdb.list_items(ci_type=type, service_id=service_id)
    return {"items": [i.as_dict() for i in items], "total": len(items)}


@itsm_router.post("/cmdb/items", status_code=201)
def create_cmdb_item(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    try:
        item = _itsm_service().cmdb.add_item(**_ci_fields(payload))
    except CmdbError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return item.as_dict()


@itsm_router.get("/cmdb/items/{ci_id}")
def get_cmdb_item(
    ci_id: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    try:
        return _itsm_service().cmdb.get_item(ci_id).as_dict()
    except CmdbError as exc:
        raise _not_found(exc) from exc


@itsm_router.put("/cmdb/items/{ci_id}")
def update_cmdb_item(
    ci_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    try:
        return _itsm_service().cmdb.update_item(ci_id, **_ci_fields(payload)).as_dict()
    except CmdbError as exc:
        raise _not_found(exc) from exc


@itsm_router.delete("/cmdb/items/{ci_id}")
def delete_cmdb_item(
    ci_id: str,
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    return {"deleted": _itsm_service().cmdb.delete_item(ci_id)}


@itsm_router.get("/cmdb/items/{ci_id}/impact")
def cmdb_impact(
    ci_id: str,
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    try:
        return _itsm_service().cmdb.impact(ci_id)
    except CmdbError as exc:
        raise _not_found(exc) from exc


@itsm_router.get("/cmdb/relationships")
def list_cmdb_relationships(
    ci_id: str = Query(default=""),
    _identity: ITSMIdentity = _ITSM_READ,
) -> dict[str, Any]:
    rels = _itsm_service().cmdb.list_relationships(ci_id=ci_id)
    return {"relationships": [r.as_dict() for r in rels], "total": len(rels)}


@itsm_router.post("/cmdb/relationships", status_code=201)
def create_cmdb_relationship(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    source_id = str(payload.get("source_id") or "").strip()
    target_id = str(payload.get("target_id") or "").strip()
    if not source_id or not target_id:
        raise HTTPException(status_code=422, detail="source_id and target_id are required")
    if source_id == target_id:
        raise HTTPException(status_code=422, detail="a CI cannot relate to itself")
    try:
        rel = _itsm_service().cmdb.relate(
            source_id, target_id, type=payload.get("type") or "depends_on"
        )
    except CmdbError as exc:
        raise _not_found(exc) from exc
    return rel.as_dict()


@itsm_router.delete("/cmdb/relationships/{relationship_id}")
def delete_cmdb_relationship(
    relationship_id: str,
    _identity: ITSMIdentity = _ITSM_MANAGE,
) -> dict[str, Any]:
    return {"deleted": _itsm_service().cmdb.unrelate(relationship_id)}


# -- BPMN workflow engine (import / customize schemes) ------------------------


@itsm_router.post("/schemes", status_code=201)
def create_scheme(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    identity: ITSMIdentity = _ITSM_ADMIN,
) -> dict[str, Any]:
    """Register a workflow scheme from its JSON form (the offline editor's save).

    The scheme is rebuilt via the engine, validated and persisted as BPMN — so the
    offline SVG editor and the BPMN import path converge on the same stored artifact.
    """

    key = str(payload.get("key") or "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="scheme key is required")
    try:
        scheme = WorkflowScheme.from_dict(payload)
        saved = _itsm_service().save_scheme(scheme, actor=identity.username)
    except SchemeValidationError as exc:
        raise HTTPException(status_code=422, detail={"problems": exc.problems}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return saved.as_dict()


@itsm_router.post("/schemes/import-bpmn", status_code=201)
def import_bpmn_scheme(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
    identity: ITSMIdentity = _ITSM_ADMIN,
) -> dict[str, Any]:
    """Upload a BPMN 2.0 process and register it as a runnable workflow scheme."""

    xml = str(payload.get("bpmn") or "").strip()
    if not xml:
        raise HTTPException(status_code=422, detail="bpmn XML is required")
    try:
        scheme = _itsm_service().import_bpmn_scheme(
            xml,
            key=str(payload.get("key") or ""),
            name=str(payload.get("name") or ""),
            actor=identity.username,
        )
    except SchemeValidationError as exc:
        raise HTTPException(status_code=422, detail={"problems": exc.problems}) from exc
    except ValueError as exc:  # BPMN parse error
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return scheme.as_dict()


@itsm_router.delete("/schemes/{key}")
def delete_scheme(
    key: str,
    _identity: ITSMIdentity = _ITSM_ADMIN,
) -> dict[str, Any]:
    try:
        deleted = _itsm_service().delete_custom_scheme(key)
    except ValueError as exc:  # built-in scheme cannot be deleted
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"deleted": deleted}


def _catalog_fields(payload: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in (
        "id",
        "name",
        "category",
        "description",
        "owner",
        "sla_id",
        "lifecycle",
        "provider",
    ):
        if key in payload and payload[key] is not None:
            fields[key] = payload[key]
    if isinstance(payload.get("tags"), (list, tuple)):
        fields["tags"] = tuple(str(tag) for tag in payload["tags"])
    return fields


def _ci_fields(payload: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in ("id", "name", "ci_type", "status", "description", "owner", "service_id"):
        if key in payload and payload[key] is not None:
            fields[key] = payload[key]
    if isinstance(payload.get("cloud"), dict):
        fields["cloud"] = payload["cloud"]
    if isinstance(payload.get("attributes"), dict):
        fields["attributes"] = payload["attributes"]
    return fields


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
            "workflow_editor_url": str(request.url_for("itsm_workflow_editor")),
        },
    )


_OFFLINE_EDITOR_ID = "bpmn-offline"


def _offline_editor(request: Request) -> dict[str, Any] | None:
    """Describe the offline editor plugin if it is loaded (else None → CDN bpmn-js)."""

    editor = get_plugin_host().editors.get(_OFFLINE_EDITOR_ID)
    if editor is None:
        return None
    return {
        "js": str(request.url_for("itsm_workflow_asset", name="bpmn_editor.js")),
        "css": str(request.url_for("itsm_workflow_asset", name="bpmn_editor.css")),
        "info": editor.initialize({}),
    }


@itsm_web_router.get(
    "/admin/itsm/workflow", response_class=HTMLResponse, name="itsm_workflow_editor"
)
def itsm_workflow_editor(
    request: Request,
    identity: ITSMIdentity = _ITSM_READ,
) -> HTMLResponse:
    """Visual workflow editor — offline plugin editor when loaded, else bpmn-js."""

    desk = _service_desk()
    itsm = _itsm_service()
    schemes = [scheme.as_dict() for scheme in desk.schemes.values()]
    return _TEMPLATES.TemplateResponse(
        request,
        "archub_itsm_workflow.html",
        {
            "title": "ArcHub ITSM · Workflow Editor",
            "current_user": identity.as_dict(),
            "schemes": schemes,
            "custom_scheme_keys": itsm.custom_scheme_keys(),
            "can_edit": identity.can(ITSMPermission.ADMIN),
            "offline_editor": _offline_editor(request),
        },
    )


@itsm_web_router.get("/admin/itsm/workflow/assets/{name}", name="itsm_workflow_asset")
def itsm_workflow_asset(name: str) -> FileResponse:
    """Serve the offline BPMN editor plugin's bundled static assets (no CDN)."""

    editor = get_plugin_host().editors.get(_OFFLINE_EDITOR_ID)
    path = getattr(editor, "asset_path", None)
    resolved = path(name) if callable(path) else None
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"unknown editor asset {name!r}")
    file_path = cast(str | os.PathLike[str], resolved)
    media = getattr(editor, "asset_media_type", lambda _n: None)(name) or "application/octet-stream"
    return FileResponse(file_path, media_type=media)
