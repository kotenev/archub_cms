"""ArcHub CMS backoffice and public rendering routes."""

from __future__ import annotations

__all__ = ["router"]

import hashlib
import json
import logging
import re
from datetime import datetime
from email.utils import formatdate, parsedate_to_datetime
from urllib.parse import quote_plus
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from archub_cms.application.delivery import DeliveryQuery, get_archub_delivery_service
from archub_cms.application.media import get_archub_media_service
from archub_cms.application.packages import get_archub_package_service
from archub_cms.application.publishing import get_archub_publishing_service
from archub_cms.services.cms import (
    ContentNode,
    ContentType,
    get_archub_cms_service,
)
from archub_cms.services.content_builder import get_archub_content_builder_service
from archub_cms.services.runtime import (
    default_runtime_import_sources,
    runtime_corpus_specs,
    sync_runtime_content,
)
from archub_cms.web._common import current_user, parse_form, templates

router = APIRouter()
_TEMPLATES = templates()
logger = logging.getLogger("archub_cms")
_PUBLIC_DELIVERY_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"
_PRIVATE_DELIVERY_CACHE_CONTROL = "private, max-age=0, must-revalidate"
_PREVIEW_DELIVERY_HEADERS = {
    "Cache-Control": "private, no-store",
    "Pragma": "no-cache",
    "X-ArcHub-Preview": "1",
}


def _guard(request: Request):
    user = current_user(request)
    if user is None:
        return None
    if bool(getattr(user, "is_admin", False)):
        return user
    if get_archub_cms_service().has_any_content_permission(str(getattr(user, "username", ""))):
        return user
    return None


def _can(user, action: str, node_id: str = "") -> bool:
    return get_archub_cms_service().can_user_perform(
        username=str(getattr(user, "username", "")),
        is_admin=bool(getattr(user, "is_admin", False)),
        action=action,
        node_id=node_id,
    )


def _permission_denied(action: str, node_id: str = "") -> JSONResponse:
    return JSONResponse(
        {
            "error": "ArcHub permission denied",
            "action": action,
            "node_id": node_id,
        },
        status_code=403,
    )


def _admin_required(user) -> bool:
    return bool(getattr(user, "is_admin", False))


def _public_member_context(request: Request) -> tuple[str, bool, tuple[str, ...]]:
    user = current_user(request)
    if user is None:
        return "", False, ()
    username = str(getattr(user, "username", "")).strip().lower()
    groups = {"authenticated"}
    if username:
        groups.update({username, f"user:{username}"})
    if bool(getattr(user, "is_admin", False)):
        groups.add("admin")
    return username, True, tuple(sorted(groups))


def _can_read_public_content(request: Request, node: ContentNode) -> bool:
    username, authenticated, groups = _public_member_context(request)
    return get_archub_cms_service().can_access_public_content(
        node.node_id,
        username=username,
        authenticated=authenticated,
        member_groups=groups,
    )


def _public_api_access_denied(request: Request, node: ContentNode) -> JSONResponse:
    _username, authenticated, _groups = _public_member_context(request)
    rule = get_archub_cms_service().get_public_access_rule(node.node_id)
    return JSONResponse(
        {
            "error": "ArcHub content access denied",
            "node_id": node.node_id,
            "route_path": node.route_path,
            "policy": rule.policy if rule else "public",
            "login_path": rule.login_path if rule else "/login",
        },
        status_code=403 if authenticated else 401,
    )


def _public_html_access_denied(request: Request, node: ContentNode):
    _username, authenticated, _groups = _public_member_context(request)
    rule = get_archub_cms_service().get_public_access_rule(node.node_id)
    if not authenticated:
        login_path = rule.login_path if rule else "/login"
        return RedirectResponse(
            f"{login_path}?next={quote_plus(str(request.url.path))}",
            status_code=302,
        )
    return HTMLResponse("ArcHub content access denied", status_code=403)


def _filter_public_delivery_tree(request: Request, payload: dict[str, object]) -> dict[str, object]:
    node_id = str(payload.get("node_id") or "")
    node = get_archub_cms_service().get_node(node_id) if node_id else None
    if node is not None and not _can_read_public_content(request, node):
        return {}
    clean = dict(payload)
    children = clean.get("children")
    if isinstance(children, list):
        clean["children"] = [
            child
            for item in children
            if isinstance(item, dict)
            for child in [_filter_public_delivery_tree(request, item)]
            if child
        ]
    return clean


def _filter_public_results(
    request: Request, results: list[dict[str, object]]
) -> list[dict[str, object]]:
    cms = get_archub_cms_service()
    filtered: list[dict[str, object]] = []
    for item in results:
        node_id = str(item.get("node_id") or "")
        node = cms.get_node(node_id) if node_id else None
        if node is None or _can_read_public_content(request, node):
            filtered.append(item)
    return filtered


def _see_other(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _content_not_found() -> JSONResponse:
    return JSONResponse({"error": "ArcHub content not found"}, status_code=404)


def _stable_delivery_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _delivery_etag(value: object) -> str:
    digest = hashlib.sha256(_stable_delivery_json(value).encode("utf-8")).hexdigest()[:32]
    return f'"archub-{digest}"'


def _timestamp_from_value(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _latest_delivery_timestamp(value: object) -> float:
    latest = 0.0
    if isinstance(value, dict):
        for key in ("published_at", "updated_at", "generated_at"):
            latest = max(latest, _timestamp_from_value(value.get(key)))
        for key in ("published_at_iso", "updated_at_iso", "generated_at_iso"):
            latest = max(latest, _timestamp_from_value(value.get(key)))
        for child in value.values():
            if isinstance(child, (dict, list, tuple)):
                latest = max(latest, _latest_delivery_timestamp(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            latest = max(latest, _latest_delivery_timestamp(child))
    return latest


def _delivery_cache_public(request: Request, node: ContentNode | None = None) -> bool:
    if current_user(request) is not None:
        return False
    if node is None:
        return True
    return get_archub_cms_service().get_public_access_rule(node.node_id) is None


def _request_content_domain(request: Request):
    host = request.headers.get("host") or request.url.hostname or ""
    return get_archub_cms_service().resolve_content_domain(host)


def _request_delivery_culture(request: Request, explicit_culture: str = "") -> str:
    clean = explicit_culture.strip()
    if clean:
        return clean
    domain = _request_content_domain(request)
    return domain.culture if domain is not None else ""


def _request_delivery_segment(request: Request, explicit_segment: str = "") -> str:
    clean = explicit_segment.strip()
    if clean:
        return clean
    return (
        request.headers.get("x-archub-segment", "").strip()
        or request.cookies.get("archub_segment", "").strip()
    )


def _request_domain_payload(request: Request) -> dict[str, object] | None:
    domain = _request_content_domain(request)
    return domain.__dict__ if domain is not None else None


def _request_delivery_start_item(request: Request, explicit_start_item: str = "") -> str:
    return explicit_start_item.strip() or request.headers.get("Start-Item", "").strip()


def _domain_root_path(request: Request, path: str) -> str:
    clean_path = path.strip()
    if clean_path and clean_path != "/cms":
        return clean_path
    domain = _request_content_domain(request)
    if domain is None or not domain.root_route_path:
        return clean_path
    return domain.root_route_path


def _delivery_cache_headers(value: object, *, public: bool) -> dict[str, str]:
    headers = {
        "ETag": _delivery_etag(value),
        "Cache-Control": _PUBLIC_DELIVERY_CACHE_CONTROL
        if public
        else _PRIVATE_DELIVERY_CACHE_CONTROL,
        "Vary": "Cookie, Authorization, Accept-Encoding",
        "X-ArcHub-Delivery-Cache": "conditional",
    }
    latest = _latest_delivery_timestamp(value)
    if latest:
        headers["Last-Modified"] = formatdate(latest, usegmt=True)
    return headers


def _request_not_modified(request: Request, headers: dict[str, str]) -> bool:
    etag = headers.get("ETag", "")
    if_none_match = request.headers.get("if-none-match", "")
    if etag and if_none_match:
        candidates = {item.strip() for item in if_none_match.split(",")}
        if "*" in candidates or etag in candidates:
            return True
    last_modified = headers.get("Last-Modified", "")
    if_modified_since = request.headers.get("if-modified-since", "")
    if last_modified and if_modified_since:
        try:
            modified_at = parsedate_to_datetime(last_modified).timestamp()
            requested_at = parsedate_to_datetime(if_modified_since).timestamp()
        except (TypeError, ValueError, IndexError, OverflowError):
            return False
        return modified_at <= requested_at + 1
    return False


def _json_delivery_response(
    request: Request, payload: dict[str, object], *, public: bool
) -> Response:
    headers = _delivery_cache_headers(payload, public=public)
    if _request_not_modified(request, headers):
        return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


def _text_delivery_response(
    request: Request,
    content: str,
    *,
    media_type: str,
    cache_seed: object,
    public: bool = True,
) -> Response:
    headers = _delivery_cache_headers(cache_seed, public=public)
    if _request_not_modified(request, headers):
        return Response(status_code=304, headers=headers)
    return Response(content=content, media_type=media_type, headers=headers)


def _datetime_local(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%dT%H:%M")


def _parse_datetime_local(value: str) -> float | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise ValueError(f"Invalid datetime value: {value}") from exc


def _split_webhook_events(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;\n]+", value) if item.strip()]


def _split_aliases(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;\n]+", value) if item.strip()]


def _slug_for_blueprint_name(value: str) -> str:
    slug = value.strip().lower().replace("ё", "е")
    slug = re.sub(r"[^0-9a-zа-я]+", "-", slug, flags=re.IGNORECASE)
    return re.sub(r"-{2,}", "-", slug).strip("-")


def _parse_schema_fields(value: str) -> list[dict[str, object]]:
    raw = value.strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("Fields schema must be a JSON array")
    fields: list[dict[str, object]] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Each field schema item must be an object")
        fields.append(item)
    return fields


def _parse_json_object(value: str) -> dict[str, object]:
    raw = value.strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Payload must be a JSON object")
    return parsed


def _sync_runtime_export(cms) -> None:
    try:
        cms.export_runtime_content()
    except Exception:
        # Publishing should not fail just because the derived runtime snapshot
        # cannot be refreshed; the admin dashboard exposes the explicit export
        # action for recovery and diagnostics.
        logger.warning("ArcHub runtime export refresh failed", exc_info=True)
    _invalidate_bot_resource_caches()


def _invalidate_bot_resource_caches() -> None:
    # Standalone ArcHub has no host process caches. Embedded hosts can call
    # their own invalidation adapter after invoking publish/export actions.
    return None


def _payload_from_form(content_type: ContentType, form: dict[str, str]) -> dict[str, object]:
    payload: dict[str, object] = {}
    builder = get_archub_content_builder_service()
    for field in content_type.fields:
        key = f"field_{field.alias}"
        if field.editor == "checkbox":
            payload[field.alias] = form.get(key, "").lower() in {"1", "true", "yes", "on"}
            continue
        if field.editor == "builder":
            blocks = builder.parse_blocks(form.get(key, "[]"), strict=True)
            payload[field.alias] = builder.serialize_blocks(blocks)
            continue
        payload[field.alias] = form.get(key, "")
    return payload


def _types_by_alias(types: list[ContentType]) -> dict[str, ContentType]:
    return {item.alias: item for item in types}


def _edit_context(
    *,
    request: Request,
    user,
    node: ContentNode | None,
    parent: ContentNode | None,
    content_type: ContentType,
    allowed_types: list[ContentType],
    error: str = "",
    initial_payload: dict[str, object] | None = None,
    initial_name: str = "",
    initial_slug: str = "",
) -> dict[str, object]:
    builder = get_archub_content_builder_service()
    builder_field = next(
        (field for field in content_type.fields if field.editor == "builder"), None
    )
    draft_payload = node.draft if node else dict(initial_payload or {})
    builder_blocks = []
    if builder_field is not None:
        raw_blocks = draft_payload.get(builder_field.alias, builder_field.default)
        builder_blocks = builder.parse_blocks(raw_blocks)
    builder_audit = builder.audit_blocks(builder_blocks) if builder_field is not None else []
    workflow = None
    if node is not None:
        try:
            workflow = get_archub_cms_service().get_workflow(node.node_id)
        except ValueError:
            workflow = None
    activity = (
        get_archub_cms_service().list_activity(node_id=node.node_id, limit=10) if node else []
    )
    variants = get_archub_cms_service().list_content_variants(node.node_id) if node else []
    lock = get_archub_cms_service().get_content_lock(node.node_id) if node else None
    access_rule = get_archub_cms_service().get_public_access_rule(node.node_id) if node else None
    preview_tokens = (
        get_archub_cms_service().list_preview_tokens(
            node_id=node.node_id,
            include_expired=True,
            limit=8,
        )
        if node
        else []
    )
    return {
        "title": "ArcHub CMS",
        "current_user": user,
        "node": node,
        "parent": parent,
        "content_type": content_type,
        "allowed_types": allowed_types,
        "draft_payload": draft_payload,
        "initial_name": initial_name,
        "initial_slug": initial_slug,
        "error": error,
        "publish_error": "",
        "validation_errors": [],
        "content_builder": {
            "enabled": builder_field is not None,
            "field_alias": builder_field.alias if builder_field else "",
            "block_types": builder.block_type_catalog(),
            "block_types_json": builder.block_type_catalog_json(),
            "blueprints": builder.blueprint_catalog(content_type.alias),
            "blueprints_json": builder.blueprint_catalog_json(content_type.alias),
            "blocks_json": builder.to_json(builder_blocks),
            "preview_html": builder.render_blocks(builder_blocks),
            "summary": builder.summary(builder_blocks),
            "audit": [issue.__dict__ for issue in builder_audit],
        },
        "workflow": workflow,
        "workflow_states": (
            "draft",
            "in_review",
            "approved",
            "changes_requested",
            "scheduled",
            "published",
            "unpublished",
            "archived",
        ),
        "workflow_publish_value": _datetime_local(workflow.scheduled_publish_at)
        if workflow
        else "",
        "workflow_unpublish_value": _datetime_local(workflow.scheduled_unpublish_at)
        if workflow
        else "",
        "activity": activity,
        "variants": variants,
        "segments": get_archub_cms_service().list_content_segments(node.node_id) if node else [],
        "preview_tokens": preview_tokens,
        "content_lock": lock,
        "access_rule": access_rule,
        "public_access_policies": get_archub_cms_service().available_public_access_policies(),
        "document_blueprints": get_archub_cms_service().list_content_blueprints(
            content_type_alias=content_type.alias,
            limit=20,
        ),
        "request": request,
    }


def _seo_context(
    request: Request, node: ContentNode, payload: dict[str, object], *, preview: bool = False
) -> dict[str, str]:
    title = str(
        payload.get("seo_title") or payload.get("title") or payload.get("hero_title") or node.name
    ).strip()
    description = str(
        payload.get("seo_description")
        or payload.get("summary")
        or payload.get("excerpt")
        or payload.get("headline")
        or payload.get("hero_text")
        or ""
    ).strip()
    canonical = str(payload.get("canonical_url") or "").strip()
    if not canonical:
        canonical = str(request.base_url).rstrip("/") + node.route_path
    og_image = str(payload.get("og_image") or payload.get("image_url") or "").strip()
    if og_image.startswith("/"):
        og_image = str(request.base_url).rstrip("/") + og_image
    return {
        "meta_title": title,
        "meta_description": description,
        "canonical_url": canonical,
        "og_title": str(payload.get("og_title") or title).strip(),
        "og_description": str(payload.get("og_description") or description).strip(),
        "og_image": og_image,
        "robots_meta": "noindex,nofollow"
        if preview
        else str(payload.get("robots_meta") or "index,follow"),
    }


@router.get("/admin/archub", response_class=HTMLResponse)
async def archub_dashboard(
    request: Request,
    content_type: str = "",
    status: str = "",
    q: str = "",
):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse"):
        return _permission_denied("browse")
    cms = get_archub_cms_service()
    builder = get_archub_content_builder_service()
    sources = default_runtime_import_sources()
    content_types = cms.list_content_types()
    filters = {
        "content_type": content_type.strip(),
        "status": status.strip(),
        "q": q.strip(),
    }
    return _TEMPLATES.TemplateResponse(
        request,
        "archub_admin.html",
        {
            "title": "ArcHub CMS",
            "current_user": user,
            "stats": cms.stats(),
            "managed_counts": cms.managed_counts(),
            "runtime_catalog": cms.runtime_catalog(
                runtime_corpus_specs(),
                sources["bot_resource_roots"],
            ),
            "delivery_cache": cms.delivery_cache_report(limit=8),
            "content_builder": {
                "block_types": builder.block_type_catalog(),
                "blueprints": builder.blueprint_catalog(),
                "total": len(builder.list_block_types()),
                "blueprint_total": len(builder.list_blueprints()),
            },
            "runtime_export": cms.runtime_export_status(),
            "runtime_audit": cms.runtime_audit_report(),
            "content_health": cms.content_health_report(),
            "preview_tokens": cms.preview_tokens_report(limit=12),
            "domain_report": cms.content_domain_report(limit=12),
            "content_model": cms.content_model_report(),
            "document_blueprints": cms.list_content_blueprints(limit=12),
            "workflow_report": cms.workflow_report(),
            "permissions_report": cms.content_permissions_report(limit=12),
            "access_report": cms.public_access_report(limit=12),
            "webhook_report": cms.webhook_report(limit=12),
            "trash": cms.list_trashed_nodes(limit=8),
            "locks": cms.list_content_locks(limit=8),
            "activity": cms.list_activity(limit=12),
            "tree": cms.list_filtered_nodes(
                content_type_alias=filters["content_type"],
                status=filters["status"],
                query=filters["q"],
            ),
            "content_types": content_types,
            "types_by_alias": _types_by_alias(content_types),
            "filters": filters,
            "runtime_exported": request.query_params.get("runtime_exported") == "1",
            "runtime_synced": request.query_params.get("runtime_synced") == "1",
            "runtime_rebuilt": request.query_params.get("runtime_rebuilt") == "1",
            "runtime_error": request.query_params.get("runtime_error", ""),
        },
    )


@router.get("/admin/archub/runtime/audit.json")
async def runtime_audit_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    report = get_archub_cms_service().runtime_audit_report()
    return JSONResponse(
        {
            **report,
            "issues": [issue.__dict__ for issue in report["issues"]],
        }
    )


@router.get("/admin/archub/content/health.json")
async def content_health_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    report = get_archub_cms_service().content_health_report()
    return JSONResponse(
        {
            **report,
            "issues": [issue.__dict__ for issue in report["issues"]],
        }
    )


@router.get("/admin/archub/delivery-cache.json")
async def delivery_cache_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse"):
        return _permission_denied("browse")
    return JSONResponse(get_archub_cms_service().delivery_cache_report(limit=100))


@router.get("/admin/archub/preview-tokens.json")
async def preview_tokens_json(
    request: Request,
    node_id: str = "",
    include_expired: bool = True,
    limit: int = 100,
):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    return JSONResponse(
        get_archub_cms_service().preview_tokens_report(
            node_id=node_id,
            include_expired=include_expired,
            limit=limit,
        )
    )


@router.get("/admin/archub/runtime/snapshot.json")
async def runtime_snapshot_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    return JSONResponse(get_archub_cms_service().runtime_snapshot())


@router.get("/admin/archub/runtime/manifest.json")
async def runtime_manifest_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    return JSONResponse(get_archub_cms_service().runtime_export_status())


@router.get("/admin/archub/packages/export.json")
async def export_content_package_json(
    request: Request,
    node_ids: str = "",
    name: str = "ArcHub package",
    include_descendants: bool = True,
):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    package = get_archub_package_service().export(
        name=name,
        node_ids=_split_aliases(node_ids),
        include_descendants=include_descendants,
        exported_by=user.username,
    )
    return JSONResponse(package.payload)


@router.post("/admin/archub/packages/inspect")
async def inspect_content_package(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    try:
        package = _parse_json_object(form.get("package_json", "{}"))
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    result = get_archub_package_service().inspect(package, actor=user.username)
    return JSONResponse(result.payload, status_code=result.status_code)


@router.post("/admin/archub/packages/plan")
async def plan_content_package_import(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    try:
        package = _parse_json_object(form.get("package_json", "{}"))
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    result = get_archub_package_service().plan_import(
        package,
        overwrite=form.get("overwrite", "").lower() in {"1", "true", "yes", "on"},
        actor=user.username,
    )
    return JSONResponse(result.payload, status_code=result.status_code)


@router.post("/admin/archub/packages/import")
async def import_content_package(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    try:
        package = _parse_json_object(form.get("package_json", "{}"))
        result = get_archub_package_service().import_package(
            package,
            imported_by=user.username,
            overwrite=form.get("overwrite", "").lower() in {"1", "true", "yes", "on"},
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(result.payload, status_code=result.status_code)


@router.get("/admin/archub/media.json")
async def media_library_json(request: Request, folder: str = "", limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "media"):
        return _permission_denied("media")
    return JSONResponse(
        get_archub_media_service().library_report(folder=folder, limit=limit).as_dict()
    )


@router.get("/admin/archub/dictionary.json")
async def dictionary_items_json(request: Request, group: str = "", limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    items = get_archub_cms_service().list_dictionary_items(group_name=group, limit=limit)
    return JSONResponse({"items": items, "total": len(items)})


@router.get("/admin/archub/content-model.json")
async def content_model_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    return JSONResponse(get_archub_cms_service().content_model_report())


@router.get("/admin/archub/data-types.json")
async def data_types_json(request: Request, limit: int = 200):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    items = get_archub_cms_service().list_data_types(limit=limit)
    return JSONResponse({"items": [item.__dict__ for item in items], "total": len(items)})


@router.post("/admin/archub/content-model/data-types")
async def upsert_data_type(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    form = await parse_form(request)
    try:
        get_archub_cms_service().upsert_data_type(
            alias=form.get("alias", ""),
            name=form.get("name", ""),
            editor=form.get("editor", "text"),
            description=form.get("description", ""),
            config=_parse_json_object(form.get("config_json", "{}")),
            validation=_parse_json_object(form.get("validation_json", "{}")),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.get("/admin/archub/templates.json")
async def templates_json(request: Request, limit: int = 200):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    items = get_archub_cms_service().list_templates(limit=limit)
    return JSONResponse({"items": [item.__dict__ for item in items], "total": len(items)})


@router.post("/admin/archub/content-model/templates")
async def upsert_template(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    form = await parse_form(request)
    try:
        get_archub_cms_service().upsert_template(
            alias=form.get("alias", ""),
            name=form.get("name", ""),
            view=form.get("view", "archub_public.html"),
            description=form.get("description", ""),
            allowed_content_type_aliases=_split_aliases(
                form.get("allowed_content_type_aliases", "")
            ),
            config=_parse_json_object(form.get("config_json", "{}")),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.get("/admin/archub/content-blueprints.json")
async def content_blueprints_json(request: Request, content_type: str = "", limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    items = get_archub_cms_service().list_content_blueprints(
        content_type_alias=content_type,
        limit=limit,
    )
    return JSONResponse({"items": [item.__dict__ for item in items], "total": len(items)})


@router.post("/admin/archub/content-blueprints")
async def upsert_content_blueprint(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    form = await parse_form(request)
    try:
        get_archub_cms_service().upsert_content_blueprint(
            blueprint_id=form.get("blueprint_id", ""),
            content_type_alias=form.get("content_type_alias", ""),
            name=form.get("name", ""),
            description=form.get("description", ""),
            payload=_parse_json_object(form.get("payload_json", "{}")),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.post("/admin/archub/content-blueprints/{blueprint_id}/delete")
async def delete_content_blueprint(request: Request, blueprint_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    get_archub_cms_service().delete_content_blueprint(blueprint_id, deleted_by=user.username)
    return _see_other("/admin/archub")


@router.post("/admin/archub/content-model/compositions")
async def upsert_content_composition(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    form = await parse_form(request)
    try:
        get_archub_cms_service().upsert_content_composition(
            alias=form.get("alias", ""),
            name=form.get("name", ""),
            description=form.get("description", ""),
            fields=_parse_schema_fields(form.get("fields_json", "[]")),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.post("/admin/archub/content-model/types")
async def upsert_content_type(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model")
    form = await parse_form(request)
    try:
        get_archub_cms_service().upsert_content_type(
            alias=form.get("alias", ""),
            name=form.get("name", ""),
            icon=form.get("icon", "□"),
            description=form.get("description", ""),
            fields=_parse_schema_fields(form.get("fields_json", "[]")),
            allowed_child_aliases=_split_aliases(form.get("allowed_child_aliases", "")),
            composition_aliases=_split_aliases(form.get("composition_aliases", "")),
            allow_at_root=form.get("allow_at_root", "").lower() in {"1", "true", "yes", "on"},
            is_element=form.get("is_element", "").lower() in {"1", "true", "yes", "on"},
            template=form.get("template", "page"),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.get("/admin/archub/redirects.json")
async def redirects_json(request: Request, active_only: bool = False, limit: int = 200):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    redirects = get_archub_cms_service().list_redirects(active_only=active_only, limit=limit)
    return JSONResponse(
        {
            "redirects": [item.__dict__ for item in redirects],
            "total": len(redirects),
        }
    )


@router.get("/admin/archub/domains.json")
async def content_domains_json(request: Request, limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    return JSONResponse(get_archub_cms_service().content_domain_report(limit=limit))


@router.post("/admin/archub/domains")
async def upsert_content_domain(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    try:
        get_archub_cms_service().upsert_content_domain(
            domain_id=form.get("domain_id", ""),
            hostname=form.get("hostname", ""),
            root_node_id=form.get("root_node_id", "root"),
            culture=form.get("culture", ""),
            is_default=form.get("is_default", "").lower() in {"1", "true", "yes", "on"},
            secure=form.get("secure", "").lower() in {"1", "true", "yes", "on"},
            sort_order=int(form.get("sort_order", "0") or 0),
            updated_by=user.username,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.post("/admin/archub/domains/{domain_id}/delete")
async def delete_content_domain(request: Request, domain_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    get_archub_cms_service().delete_content_domain(domain_id, deleted_by=user.username)
    return _see_other("/admin/archub")


@router.post("/admin/archub/redirects")
async def upsert_redirect_rule(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    cms = get_archub_cms_service()
    try:
        redirect = cms.upsert_redirect(
            source_path=form.get("source_path", ""),
            target_path=form.get("target_path", ""),
            status_code=int(form.get("status_code", "301") or 301),
            active=form.get("active", "1").lower() in {"1", "true", "yes", "on"},
            note=form.get("note", ""),
            updated_by=user.username,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(redirect.__dict__)


@router.get("/admin/archub/content/references.json")
async def content_reference_graph_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse"):
        return _permission_denied("browse")
    return JSONResponse(get_archub_cms_service().content_reference_graph())


@router.get("/admin/archub/activity.json")
async def activity_json(
    request: Request,
    node_id: str = "",
    action: str = "",
    actor: str = "",
    limit: int = 100,
):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse"):
        return _permission_denied("browse")
    items = get_archub_cms_service().list_activity(
        node_id=node_id,
        action=action,
        actor=actor,
        limit=limit,
    )
    return JSONResponse({"items": [item.__dict__ for item in items], "total": len(items)})


@router.get("/admin/archub/trash.json")
async def trash_json(request: Request, limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "delete"):
        return _permission_denied("delete")
    items = get_archub_cms_service().list_trashed_nodes(limit=limit)
    return JSONResponse({"items": items, "total": len(items)})


@router.get("/admin/archub/permissions.json")
async def content_permissions_json(request: Request, subject: str = "", limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _admin_required(user):
        return _permission_denied("admin")
    if subject.strip():
        items = get_archub_cms_service().list_content_permissions(subject=subject, limit=limit)
        return JSONResponse(
            {
                "actions": list(get_archub_cms_service().available_permission_actions()),
                "items": [item.__dict__ for item in items],
                "total": len(items),
            }
        )
    return JSONResponse(get_archub_cms_service().content_permissions_report(limit=limit))


@router.post("/admin/archub/permissions")
async def grant_content_permission(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _admin_required(user):
        return _permission_denied("admin")
    form = await parse_form(request)
    try:
        get_archub_cms_service().grant_content_permission(
            subject=form.get("subject", ""),
            scope_node_id=form.get("scope_node_id", ""),
            actions=_split_aliases(form.get("actions", "")),
            include_descendants=form.get("include_descendants", "").lower()
            in {"1", "true", "yes", "on"},
            note=form.get("note", ""),
            updated_by=user.username,
            rule_id=form.get("rule_id", ""),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.post("/admin/archub/permissions/{rule_id}/delete")
async def revoke_content_permission(request: Request, rule_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _admin_required(user):
        return _permission_denied("admin")
    get_archub_cms_service().revoke_content_permission(rule_id, revoked_by=user.username)
    return _see_other("/admin/archub")


@router.get("/admin/archub/access.json")
async def public_access_rules_json(request: Request, limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    return JSONResponse(get_archub_cms_service().public_access_report(limit=limit))


@router.get("/admin/archub/locks.json")
async def content_locks_json(request: Request, active_only: bool = True, limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse"):
        return _permission_denied("browse")
    items = get_archub_cms_service().list_content_locks(active_only=active_only, limit=limit)
    return JSONResponse({"items": [item.__dict__ for item in items], "total": len(items)})


@router.get("/admin/archub/webhooks.json")
async def webhooks_json(request: Request, active_only: bool = False, limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    webhooks = get_archub_cms_service().list_webhooks(active_only=active_only, limit=limit)
    return JSONResponse({"items": [item.__dict__ for item in webhooks], "total": len(webhooks)})


@router.post("/admin/archub/webhooks")
async def upsert_webhook(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    cms = get_archub_cms_service()
    try:
        cms.upsert_webhook(
            webhook_id=form.get("webhook_id", ""),
            name=form.get("name", ""),
            target_url=form.get("target_url", ""),
            events=_split_webhook_events(form.get("events", "")),
            secret=form.get("secret", ""),
            active=form.get("active", "").lower() in {"1", "true", "yes", "on"},
            timeout_seconds=float(form.get("timeout_seconds", "5") or 5),
            max_attempts=int(form.get("max_attempts", "5") or 5),
            updated_by=user.username,
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.get("/admin/archub/webhooks/deliveries.json")
async def webhook_deliveries_json(
    request: Request,
    status: str = "",
    webhook_id: str = "",
    event_type: str = "",
    limit: int = 100,
):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    deliveries = get_archub_cms_service().list_webhook_deliveries(
        status=status,
        webhook_id=webhook_id,
        event_type=event_type,
        limit=limit,
    )
    return JSONResponse(
        {
            "items": [item.__dict__ for item in deliveries],
            "total": len(deliveries),
        }
    )


@router.post("/admin/archub/webhooks/dispatch")
async def dispatch_webhook_deliveries(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    result = get_archub_cms_service().dispatch_webhook_deliveries()
    return JSONResponse(result)


@router.get("/admin/archub/workflow.json")
async def workflow_report_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "workflow"):
        return _permission_denied("workflow")
    return JSONResponse(get_archub_cms_service().workflow_report())


@router.post("/admin/archub/workflow/apply-due")
async def apply_due_workflows(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "workflow"):
        return _permission_denied("workflow")
    result = get_archub_publishing_service().apply_due_workflows(actor=user.username)
    return JSONResponse(result.report)


@router.post("/admin/archub/runtime/export")
async def export_runtime_content(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    cms = get_archub_cms_service()
    try:
        cms.export_runtime_content(exported_by=user.username)
    except Exception as exc:
        return _see_other(f"/admin/archub?runtime_error={type(exc).__name__}")
    _invalidate_bot_resource_caches()
    return _see_other("/admin/archub?runtime_exported=1")


@router.post("/admin/archub/runtime/sync")
async def sync_runtime_sources(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    cms = get_archub_cms_service()
    try:
        sync_runtime_content(cms, created_by=user.username)
    except Exception as exc:
        return _see_other(f"/admin/archub?runtime_error={type(exc).__name__}")
    _invalidate_bot_resource_caches()
    return _see_other("/admin/archub?runtime_synced=1")


@router.post("/admin/archub/runtime/rebuild-rag")
async def rebuild_runtime_rag(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings"):
        return _permission_denied("settings")
    form = await parse_form(request)
    cms = get_archub_cms_service()
    try:
        cms.rebuild_exported_rag_indexes(
            corpus_key=form.get("corpus_key", "").strip() or None,
            model=form.get("model", "").strip() or None,
        )
    except Exception as exc:
        return _see_other(f"/admin/archub?runtime_error={type(exc).__name__}")
    return _see_other("/admin/archub?runtime_rebuilt=1")


@router.get("/admin/archub/content-builder/blocks.json")
async def content_builder_blocks_json(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    builder = get_archub_content_builder_service()
    return JSONResponse(
        {
            "block_types": builder.block_type_catalog(),
            "total": len(builder.list_block_types()),
        }
    )


@router.get("/admin/archub/content-builder/blueprints.json")
async def content_builder_blueprints_json(request: Request, content_type: str = ""):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    builder = get_archub_content_builder_service()
    blueprints = builder.blueprint_catalog(content_type)
    return JSONResponse(
        {
            "blueprints": blueprints,
            "total": len(blueprints),
        }
    )


@router.post("/admin/archub/content-builder/preview")
async def preview_content_builder_blocks(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    form = await parse_form(request)
    builder = get_archub_content_builder_service()
    try:
        blocks = builder.parse_blocks(form.get("blocks", "[]"), strict=True)
    except ValueError as exc:
        return JSONResponse({"error": str(exc), "html": ""}, status_code=400)
    return JSONResponse(
        {
            "html": builder.render_blocks(blocks),
            "summary": builder.summary(blocks),
            "audit": [issue.__dict__ for issue in builder.audit_blocks(blocks)],
        }
    )


@router.post("/admin/archub/content-builder/audit")
async def audit_content_builder_blocks(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    form = await parse_form(request)
    builder = get_archub_content_builder_service()
    try:
        blocks = builder.parse_blocks(form.get("blocks", "[]"), strict=True)
    except ValueError as exc:
        return JSONResponse({"error": str(exc), "audit": []}, status_code=400)
    issues = builder.audit_blocks(blocks)
    return JSONResponse(
        {
            "summary": builder.summary(blocks),
            "audit": [issue.__dict__ for issue in issues],
        }
    )


@router.get("/admin/archub/content/new", response_class=HTMLResponse)
async def new_content(
    request: Request,
    parent_id: str = "root",
    content_type: str = "",
    blueprint_id: str = "",
):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "create", parent_id or "root"):
        return _permission_denied("create", parent_id or "root")
    cms = get_archub_cms_service()
    parent = cms.get_node(parent_id) if parent_id else None
    allowed_types = cms.allowed_child_types(parent_id or None)
    selected = cms.get_content_type(content_type) if content_type else None
    if selected is None or selected.alias not in {item.alias for item in allowed_types}:
        selected = allowed_types[0] if allowed_types else None
    if selected is None:
        return _see_other("/admin/archub")
    blueprint = cms.get_content_blueprint(blueprint_id) if blueprint_id.strip() else None
    initial_payload: dict[str, object] | None = None
    initial_name = ""
    initial_slug = ""
    if blueprint is not None and blueprint.content_type_alias == selected.alias:
        initial_payload = blueprint.payload
        initial_name = blueprint.name
        initial_slug = _slug_for_blueprint_name(blueprint.name)
    return _TEMPLATES.TemplateResponse(
        request,
        "archub_edit.html",
        _edit_context(
            request=request,
            user=user,
            node=None,
            parent=parent,
            content_type=selected,
            allowed_types=allowed_types,
            initial_payload=initial_payload,
            initial_name=initial_name,
            initial_slug=initial_slug,
        ),
    )


@router.post("/admin/archub/content", response_class=HTMLResponse)
async def create_content(request: Request):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    form = await parse_form(request)
    cms = get_archub_cms_service()
    parent_id = form.get("parent_id") or None
    if not _can(user, "create", parent_id or "root"):
        return _permission_denied("create", parent_id or "root")
    content_type_alias = form.get("content_type_alias", "")
    selected = cms.get_content_type(content_type_alias)
    if selected is None:
        return _see_other("/admin/archub")
    try:
        node = cms.create_node(
            parent_id=parent_id,
            content_type_alias=selected.alias,
            name=form.get("name", ""),
            slug=form.get("slug", ""),
            payload=_payload_from_form(selected, form),
            created_by=user.username,
        )
    except ValueError as exc:
        return _TEMPLATES.TemplateResponse(
            request,
            "archub_edit.html",
            _edit_context(
                request=request,
                user=user,
                node=None,
                parent=cms.get_node(parent_id) if parent_id else None,
                content_type=selected,
                allowed_types=cms.allowed_child_types(parent_id),
                error=str(exc),
            ),
            status_code=400,
        )
    return _see_other(f"/admin/archub/content/{node.node_id}?saved=1")


@router.get("/admin/archub/content/{node_id}", response_class=HTMLResponse)
async def edit_content(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    cms = get_archub_cms_service()
    node = cms.get_node(node_id)
    if node is None:
        return _see_other("/admin/archub")
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    content_type = cms.get_content_type(node.content_type_alias)
    if content_type is None:
        return _see_other("/admin/archub")
    parent = cms.get_node(node.parent_id) if node.parent_id else None
    return _TEMPLATES.TemplateResponse(
        request,
        "archub_edit.html",
        {
            **_edit_context(
                request=request,
                user=user,
                node=node,
                parent=parent,
                content_type=content_type,
                allowed_types=cms.allowed_child_types(node.parent_id),
            ),
            "versions": cms.list_versions(node_id),
            "saved": request.query_params.get("saved") == "1",
            "published": request.query_params.get("published") == "1",
            "publish_error": request.query_params.get("publish_error", ""),
            "validation_errors": cms.validate_node_draft(node_id),
        },
    )


@router.get("/admin/archub/content/{node_id}/preview", response_class=HTMLResponse)
async def preview_content_draft(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    cms = get_archub_cms_service()
    node = cms.get_node(node_id)
    if node is None:
        return _see_other("/admin/archub")
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    content_type = cms.get_content_type(node.content_type_alias)
    if content_type is None:
        return _see_other("/admin/archub")
    builder = get_archub_content_builder_service()
    builder_blocks = builder.parse_blocks(node.draft.get("builder_blocks"))
    return _TEMPLATES.TemplateResponse(
        request,
        "archub_public.html",
        {
            "title": node.draft.get("seo_title") or node.draft.get("title") or node.name,
            **_seo_context(request, node, node.draft, preview=True),
            "node": node,
            "content_type": content_type,
            "payload": node.draft,
            "builder_blocks": builder_blocks,
            "rendered_blocks": builder.render_blocks(builder_blocks),
            "children": cms.published_children(node.node_id),
            "current_user": user,
            "preview": True,
        },
    )


@router.get("/admin/archub/content/{node_id}/references.json")
async def content_references_json(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    try:
        return JSONResponse(get_archub_cms_service().content_references(node_id))
    except ValueError:
        return JSONResponse({"error": "Content node not found"}, status_code=404)


@router.get("/admin/archub/content/{node_id}/workflow.json")
async def content_workflow_json(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    try:
        workflow = get_archub_cms_service().get_workflow(node_id)
    except ValueError:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    return JSONResponse(workflow.__dict__)


@router.get("/admin/archub/content/{node_id}/activity.json")
async def content_activity_json(request: Request, node_id: str, limit: int = 100):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    if get_archub_cms_service().get_node(node_id) is None:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    items = get_archub_cms_service().list_activity(node_id=node_id, limit=limit)
    return JSONResponse({"items": [item.__dict__ for item in items], "total": len(items)})


@router.get("/admin/archub/content/{node_id}/lock.json")
async def content_lock_json(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    if get_archub_cms_service().get_node(node_id) is None:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    lock = get_archub_cms_service().get_content_lock(node_id)
    return JSONResponse(lock.__dict__ if lock is not None else {})


@router.get("/admin/archub/content/{node_id}/preview-tokens.json")
async def content_preview_tokens_json(request: Request, node_id: str, include_expired: bool = True):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    if get_archub_cms_service().get_node(node_id) is None:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    return JSONResponse(
        get_archub_cms_service().preview_tokens_report(
            node_id=node_id,
            include_expired=include_expired,
            limit=100,
        )
    )


@router.post("/admin/archub/content/{node_id}/preview-tokens")
async def create_content_preview_token(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    form = await parse_form(request)
    try:
        payload = get_archub_cms_service().create_preview_token(
            node_id,
            created_by=user.username,
            ttl_seconds=float(form.get("ttl_seconds", "3600") or 3600),
            note=form.get("note", ""),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if form.get("redirect", "").lower() in {"1", "true", "yes", "on"}:
        return _see_other(f"/admin/archub/content/{node_id}?saved=1")
    return JSONResponse(payload)


@router.post("/admin/archub/preview-tokens/{token_hash}/revoke")
async def revoke_content_preview_token(request: Request, token_hash: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    cms = get_archub_cms_service()
    token = cms.get_preview_token(token_hash)
    if token is None:
        return JSONResponse({"error": "Preview token not found"}, status_code=404)
    if not _can(user, "update", token.node_id):
        return _permission_denied("update", token.node_id)
    revoked = cms.revoke_preview_token(token_hash, revoked_by=user.username)
    if not revoked:
        return JSONResponse({"error": "Preview token not found"}, status_code=404)
    form = await parse_form(request)
    if form.get("redirect", "").lower() in {"1", "true", "yes", "on"}:
        return _see_other("/admin/archub")
    return JSONResponse({"revoked": True, "token_hash": token_hash})


@router.get("/admin/archub/content/{node_id}/access.json")
async def content_public_access_json(request: Request, node_id: str, inherited: bool = True):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    try:
        rule = get_archub_cms_service().get_public_access_rule(node_id, inherited=inherited)
    except ValueError:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    return JSONResponse(rule.__dict__ if rule is not None else {"policy": "public"})


@router.post("/admin/archub/content/{node_id}/access")
async def update_content_public_access(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings", node_id):
        return _permission_denied("settings", node_id)
    form = await parse_form(request)
    try:
        get_archub_cms_service().set_public_access_rule(
            node_id,
            policy=form.get("policy", "public"),
            member_groups=_split_aliases(form.get("member_groups", "")),
            include_descendants=form.get("include_descendants", "").lower()
            in {"1", "true", "yes", "on"},
            login_path=form.get("login_path", "/login"),
            denied_path=form.get("denied_path", ""),
            note=form.get("note", ""),
            updated_by=user.username,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if form.get("redirect", "").lower() in {"1", "true", "yes", "on"}:
        return _see_other(f"/admin/archub/content/{node_id}?saved=1")
    rule = get_archub_cms_service().get_public_access_rule(node_id, inherited=False)
    return JSONResponse(rule.__dict__ if rule is not None else {"policy": "public"})


@router.post("/admin/archub/content/{node_id}/access/delete")
async def remove_content_public_access(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "settings", node_id):
        return _permission_denied("settings", node_id)
    get_archub_cms_service().remove_public_access_rule(node_id, updated_by=user.username)
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/lock")
async def acquire_content_lock(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    form = await parse_form(request)
    try:
        lock = get_archub_cms_service().acquire_content_lock(
            node_id,
            owner=user.username,
            ttl_seconds=float(form.get("ttl_seconds", "1800") or 1800),
            note=form.get("note", ""),
            force=form.get("force", "").lower() in {"1", "true", "yes", "on"},
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if form.get("redirect", "").lower() in {"1", "true", "yes", "on"}:
        return _see_other(f"/admin/archub/content/{node_id}?saved=1")
    return JSONResponse(lock.__dict__)


@router.post("/admin/archub/content/{node_id}/unlock")
async def release_content_lock(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    form = await parse_form(request)
    try:
        get_archub_cms_service().release_content_lock(
            node_id,
            owner=user.username,
            force=form.get("force", "").lower() in {"1", "true", "yes", "on"},
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if form.get("redirect", "").lower() in {"1", "true", "yes", "on"}:
        return _see_other(f"/admin/archub/content/{node_id}?saved=1")
    return JSONResponse({"released": True})


@router.get("/admin/archub/content/{node_id}/variants.json")
async def content_variants_json(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    try:
        variants = get_archub_cms_service().list_content_variants(node_id)
    except ValueError:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    return JSONResponse({"items": [item.__dict__ for item in variants], "total": len(variants)})


@router.post("/admin/archub/content/{node_id}/variants")
async def upsert_content_variant(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    form = await parse_form(request)
    try:
        variant = get_archub_cms_service().upsert_content_variant(
            node_id,
            culture=form.get("culture", ""),
            payload=_parse_json_object(form.get("payload_json", "{}")),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if form.get("publish", "").lower() in {"1", "true", "yes", "on"}:
        try:
            variant = get_archub_cms_service().publish_content_variant(
                node_id,
                culture=variant.culture,
                published_by=user.username,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/variants/{culture}/publish")
async def publish_content_variant(request: Request, node_id: str, culture: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "publish", node_id):
        return _permission_denied("publish", node_id)
    try:
        get_archub_cms_service().publish_content_variant(
            node_id,
            culture=culture,
            published_by=user.username,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other(f"/admin/archub/content/{node_id}?published=1")


@router.get("/admin/archub/content/{node_id}/segments.json")
async def content_segments_json(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    try:
        segments = get_archub_cms_service().list_content_segments(node_id)
    except ValueError:
        return JSONResponse({"error": "Content node not found"}, status_code=404)
    return JSONResponse({"items": [item.__dict__ for item in segments], "total": len(segments)})


@router.post("/admin/archub/content/{node_id}/segments")
async def upsert_content_segment(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    form = await parse_form(request)
    try:
        segment = get_archub_cms_service().upsert_content_segment(
            node_id,
            segment=form.get("segment", ""),
            payload=_parse_json_object(form.get("payload_json", "{}")),
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if form.get("publish", "").lower() in {"1", "true", "yes", "on"}:
        try:
            get_archub_cms_service().publish_content_segment(
                node_id,
                segment=segment.segment,
                published_by=user.username,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/segments/{segment}/publish")
async def publish_content_segment(request: Request, node_id: str, segment: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "publish", node_id):
        return _permission_denied("publish", node_id)
    try:
        get_archub_cms_service().publish_content_segment(
            node_id,
            segment=segment,
            published_by=user.username,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other(f"/admin/archub/content/{node_id}?published=1")


@router.post("/admin/archub/content/{node_id}/blueprints")
async def save_content_as_blueprint(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "model"):
        return _permission_denied("model", node_id)
    cms = get_archub_cms_service()
    node = cms.get_node(node_id)
    if node is None:
        return _content_not_found()
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    form = await parse_form(request)
    try:
        payload = (
            _parse_json_object(form.get("payload_json", "{}"))
            if form.get("payload_json", "").strip()
            else dict(node.draft)
        )
        cms.upsert_content_blueprint(
            blueprint_id=form.get("blueprint_id", ""),
            content_type_alias=node.content_type_alias,
            name=form.get("name") or node.name,
            description=form.get("description", ""),
            payload=payload,
            updated_by=user.username,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.get("/admin/archub/content/{node_id}/versions/{version_no}/json")
async def content_version_json(request: Request, node_id: str, version_no: int):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "browse", node_id):
        return _permission_denied("browse", node_id)
    versions = get_archub_cms_service().list_versions(node_id, limit=500)
    for version in versions:
        if version.version_no == version_no:
            return JSONResponse(version.__dict__)
    return JSONResponse({"error": "Content version not found"}, status_code=404)


@router.post("/admin/archub/content/{node_id}", response_class=HTMLResponse)
async def update_content(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    form = await parse_form(request)
    cms = get_archub_cms_service()
    node = cms.get_node(node_id)
    if node is None:
        return _see_other("/admin/archub")
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    content_type = cms.get_content_type(node.content_type_alias)
    if content_type is None:
        return _see_other("/admin/archub")
    try:
        updated = cms.update_node(
            node_id,
            name=form.get("name", ""),
            slug=form.get("slug", ""),
            payload=_payload_from_form(content_type, form),
            updated_by=user.username,
        )
    except ValueError as exc:
        return _TEMPLATES.TemplateResponse(
            request,
            "archub_edit.html",
            {
                **_edit_context(
                    request=request,
                    user=user,
                    node=node,
                    parent=cms.get_node(node.parent_id) if node.parent_id else None,
                    content_type=content_type,
                    allowed_types=cms.allowed_child_types(node.parent_id),
                    error=str(exc),
                ),
                "versions": cms.list_versions(node_id),
            },
            status_code=400,
        )
    return _see_other(f"/admin/archub/content/{updated.node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/publish")
async def publish_content(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "publish", node_id):
        return _permission_denied("publish", node_id)
    try:
        get_archub_publishing_service().publish(node_id, actor=user.username)
    except ValueError as exc:
        return _see_other(f"/admin/archub/content/{node_id}?publish_error={quote_plus(str(exc))}")
    return _see_other(f"/admin/archub/content/{node_id}?published=1")


@router.post("/admin/archub/content/{node_id}/unpublish")
async def unpublish_content(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "publish", node_id):
        return _permission_denied("publish", node_id)
    try:
        get_archub_publishing_service().unpublish(node_id, actor=user.username)
    except ValueError:
        return _see_other(f"/admin/archub/content/{node_id}")
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/duplicate")
async def duplicate_content(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    cms = get_archub_cms_service()
    source = cms.get_node(node_id)
    if source is None:
        return _see_other("/admin/archub")
    if not _can(user, "create", source.parent_id or "root"):
        return _permission_denied("create", source.parent_id or "root")
    try:
        duplicate = cms.duplicate_node(node_id, created_by=user.username)
    except ValueError:
        return _see_other(f"/admin/archub/content/{node_id}")
    return _see_other(f"/admin/archub/content/{duplicate.node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/workflow")
async def update_content_workflow(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "workflow", node_id):
        return _permission_denied("workflow", node_id)
    form = await parse_form(request)
    try:
        get_archub_publishing_service().update_workflow(
            node_id=node_id,
            state=form.get("state", "draft"),
            assigned_to=form.get("assigned_to", ""),
            scheduled_publish_at=_parse_datetime_local(form.get("scheduled_publish_at", "")),
            scheduled_unpublish_at=_parse_datetime_local(form.get("scheduled_unpublish_at", "")),
            note=form.get("note", ""),
            actor=user.username,
        )
    except ValueError as exc:
        return _see_other(f"/admin/archub/content/{node_id}?publish_error={quote_plus(str(exc))}")
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/versions/{version_no}/restore")
async def restore_content_version(request: Request, node_id: str, version_no: int):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "update", node_id):
        return _permission_denied("update", node_id)
    cms = get_archub_cms_service()
    try:
        cms.restore_version(node_id, version_no, updated_by=user.username)
    except ValueError as exc:
        return _see_other(f"/admin/archub/content/{node_id}?publish_error={quote_plus(str(exc))}")
    return _see_other(f"/admin/archub/content/{node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/delete")
async def delete_content(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "delete", node_id):
        return _permission_denied("delete", node_id)
    try:
        get_archub_publishing_service().delete(node_id, actor=user.username)
    except ValueError:
        return _see_other(f"/admin/archub/content/{node_id}")
    return _see_other("/admin/archub")


@router.post("/admin/archub/content/{node_id}/restore-from-trash")
async def restore_content_from_trash(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "delete", node_id):
        return _permission_denied("delete", node_id)
    try:
        result = get_archub_publishing_service().restore_from_trash(node_id, actor=user.username)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    restored = result.node
    if restored is None:
        return JSONResponse({"error": "ArcHub content restore failed"}, status_code=500)
    return _see_other(f"/admin/archub/content/{restored.node_id}?saved=1")


@router.post("/admin/archub/content/{node_id}/purge")
async def purge_content_from_trash(request: Request, node_id: str):
    user = _guard(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _can(user, "delete", node_id):
        return _permission_denied("delete", node_id)
    try:
        get_archub_publishing_service().purge(node_id, actor=user.username)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _see_other("/admin/archub")


@router.get("/cms/api/preview/{token}")
async def cms_preview_api(request: Request, token: str, include_children: bool = False):
    payload = get_archub_cms_service().resolve_preview_token(
        token,
        include_children=include_children,
    )
    if payload is None:
        return JSONResponse(
            {"error": "ArcHub preview token not found"},
            status_code=404,
            headers=_PREVIEW_DELIVERY_HEADERS,
        )
    return JSONResponse(payload, headers=_PREVIEW_DELIVERY_HEADERS)


@router.get("/cms/api/tree")
async def cms_tree_api(
    request: Request,
    culture: str = "",
    segment: str = "",
    fields: str = "",
    expand: str = "",
    start_item: str = "",
):
    domain = _request_content_domain(request)
    resolved_culture = _request_delivery_culture(request, culture)
    resolved_segment = _request_delivery_segment(request, segment)
    delivery = get_archub_delivery_service()
    try:
        root_node_id = delivery.resolve_start_node_id(
            _request_delivery_start_item(request, start_item),
            fallback=domain.root_node_id if domain is not None else "root",
        )
        payload = delivery.tree(
            DeliveryQuery(
                culture=resolved_culture,
                segment=resolved_segment,
                fields=fields,
                expand=expand,
            ),
            root_node_id=root_node_id,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    filtered = _filter_public_delivery_tree(request, payload)
    if filtered and domain is not None:
        filtered["domain"] = domain.__dict__
    return _json_delivery_response(request, filtered, public=_delivery_cache_public(request))


@router.get("/cms/api/search")
async def cms_search_api(
    request: Request,
    q: str = "",
    content_type: str = "",
    tag: str = "",
    limit: int = 20,
    culture: str = "",
    segment: str = "",
    fields: str = "",
):
    resolved_culture = _request_delivery_culture(request, culture)
    resolved_segment = _request_delivery_segment(request, segment)
    try:
        results = get_archub_delivery_service().search(
            q,
            content_type_alias=content_type,
            tag=tag,
            limit=limit,
            query=DeliveryQuery(
                culture=resolved_culture,
                segment=resolved_segment,
                fields=fields,
            ),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    results = _filter_public_results(request, results)
    payload = {
        "query": q,
        "content_type": content_type,
        "tag": tag,
        "culture": resolved_culture,
        "segment": resolved_segment,
        "domain": _request_domain_payload(request),
        "results": results,
        "total": len(results),
    }
    return _json_delivery_response(request, payload, public=_delivery_cache_public(request))


@router.get("/cms/api/tags")
async def cms_tags_api(request: Request):
    results = _filter_public_results(request, get_archub_cms_service().published_search(limit=100))
    tags_by_key: dict[str, dict[str, object]] = {}
    for result in results:
        tags = result.get("tags")
        if not isinstance(tags, (list, tuple)):
            continue
        for tag in tags:
            key = str(tag).casefold()
            row = tags_by_key.setdefault(
                key, {"tag": tag, "slug": key.replace(" ", "-"), "count": 0}
            )
            row["count"] = int(row["count"]) + 1  # type: ignore[arg-type]
    tags = sorted(
        tags_by_key.values(), key=lambda item: (-int(item["count"]), str(item["tag"]).casefold())
    )
    return _json_delivery_response(
        request, {"tags": tags, "total": len(tags)}, public=_delivery_cache_public(request)
    )


@router.get("/cms/api/tags/{tag}")
async def cms_tag_api(request: Request, tag: str, limit: int = 50):
    results = get_archub_cms_service().published_by_tag(tag, limit=limit)
    results = _filter_public_results(request, results)
    payload = {"tag": tag, "results": results, "total": len(results)}
    return _json_delivery_response(request, payload, public=_delivery_cache_public(request))


@router.get("/cms/api/content")
async def cms_content_api_root(
    request: Request,
    path: str = "/cms",
    culture: str = "",
    segment: str = "",
    fields: str = "",
    expand: str = "",
    include_children: bool = True,
):
    target_path = _domain_root_path(request, path)
    node = get_archub_cms_service().get_published_by_path(target_path)
    if node is None:
        return _content_not_found()
    if not _can_read_public_content(request, node):
        return _public_api_access_denied(request, node)
    try:
        payload = get_archub_delivery_service().content(
            target_path,
            DeliveryQuery(
                include_children=include_children,
                culture=_request_delivery_culture(request, culture),
                segment=_request_delivery_segment(request, segment),
                fields=fields,
                expand=expand,
            ),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if payload is None:
        return _content_not_found()
    payload["domain"] = _request_domain_payload(request)
    return _json_delivery_response(request, payload, public=_delivery_cache_public(request, node))


@router.get("/cms/api/content/{path:path}")
async def cms_content_api(
    request: Request,
    path: str,
    culture: str = "",
    segment: str = "",
    fields: str = "",
    expand: str = "",
    include_children: bool = True,
):
    route_path = "/cms/" + path.strip("/")
    node = get_archub_cms_service().get_published_by_path(route_path)
    if node is None:
        return _content_not_found()
    if not _can_read_public_content(request, node):
        return _public_api_access_denied(request, node)
    try:
        payload = get_archub_delivery_service().content(
            route_path,
            DeliveryQuery(
                include_children=include_children,
                culture=_request_delivery_culture(request, culture),
                segment=_request_delivery_segment(request, segment),
                fields=fields,
                expand=expand,
            ),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if payload is None:
        return _content_not_found()
    payload["domain"] = _request_domain_payload(request)
    return _json_delivery_response(request, payload, public=_delivery_cache_public(request, node))


def _feed_xml(request: Request) -> Response:
    cms = get_archub_cms_service()
    base_url = str(request.base_url).rstrip("/")
    items = [
        item
        for item in cms.published_feed(base_url=base_url)
        if (node := cms.get_published_by_path(str(item["link"]).replace(base_url, ""))) is not None
        and _can_read_public_content(request, node)
    ]
    entries = "\n".join(
        "    <item>"
        f"<title>{escape(item['title'])}</title>"
        f"<link>{escape(item['link'])}</link>"
        f"<guid>{escape(item['guid'])}</guid>"
        f"<description>{escape(item['description'])}</description>"
        f"<pubDate>{formatdate(float(item['published_at']), usegmt=True)}</pubDate>"
        f"<category>{escape(', '.join(item['tags']))}</category>"
        "</item>"
        for item in items
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>"
        "<title>ArcHub CMS Feed</title>"
        f"<link>{escape(base_url + '/cms')}</link>"
        "<description>Published ArcHub CMS content</description>"
        f"{entries}"
        "  </channel>\n"
        "</rss>\n"
    )
    return _text_delivery_response(
        request,
        xml,
        media_type="application/rss+xml",
        cache_seed={"feed": items, "base_url": base_url},
        public=_delivery_cache_public(request),
    )


@router.get("/cms/feed.xml")
async def cms_feed_xml(request: Request):
    return _feed_xml(request)


@router.get("/feed.xml")
async def site_feed_xml(request: Request):
    return _feed_xml(request)


@router.get("/sitemap.xml")
async def sitemap_xml(request: Request):
    cms = get_archub_cms_service()
    base_url = str(request.base_url).rstrip("/")
    items = [
        item
        for item in cms.published_sitemap(base_url=base_url)
        if (node := cms.get_published_by_path(str(item["loc"]).replace(base_url, ""))) is not None
        and _can_read_public_content(request, node)
    ]
    urls = "\n".join(
        "  <url>"
        f"<loc>{escape(item['loc'])}</loc>"
        f"<lastmod>{escape(item['lastmod'])}</lastmod>"
        f"<priority>{escape(item['priority'])}</priority>"
        "</url>"
        for item in items
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return _text_delivery_response(
        request,
        xml,
        media_type="application/xml",
        cache_seed={"sitemap": items, "base_url": base_url},
        public=_delivery_cache_public(request),
    )


@router.get("/robots.txt")
async def robots_txt(request: Request):
    base_url = str(request.base_url).rstrip("/")
    text = f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n"
    return _text_delivery_response(
        request,
        text,
        media_type="text/plain",
        cache_seed={"robots": text},
        public=True,
    )


@router.get("/cms", response_class=HTMLResponse)
async def cms_root(request: Request):
    return await _render_public_content(request, "")


@router.get("/cms/{path:path}", response_class=HTMLResponse)
async def cms_page(request: Request, path: str):
    return await _render_public_content(request, path)


async def _render_public_content(request: Request, path: str):
    cms = get_archub_cms_service()
    culture = _request_delivery_culture(request, request.query_params.get("culture", ""))
    segment = _request_delivery_segment(request, request.query_params.get("segment", ""))
    node = cms.get_published_by_path(_domain_root_path(request, path))
    if node is None:
        redirect = cms.resolve_redirect(path)
        if redirect is not None:
            return RedirectResponse(redirect.target_path, status_code=redirect.status_code)
        return HTMLResponse("ArcHub content not found", status_code=404)
    if not _can_read_public_content(request, node):
        return _public_html_access_denied(request, node)
    content_type = cms.get_content_type(node.content_type_alias)
    if content_type is None:
        return HTMLResponse("ArcHub content type not found", status_code=404)
    template = cms.get_template(content_type.template)
    template_name = template.view if template is not None else "archub_public.html"
    try:
        public_payload = (
            cms.published_content_payload(
                node.route_path,
                culture=culture,
                segment=segment,
            )
            or {}
        )
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)
    cache_headers = _delivery_cache_headers(
        {
            "content": public_payload,
            "template": content_type.template,
            "template_config": template.config if template else {},
            "domain": _request_domain_payload(request),
            "segment": segment,
        },
        public=_delivery_cache_public(request, node),
    )
    if _request_not_modified(request, cache_headers):
        return Response(status_code=304, headers=cache_headers)
    payload = public_payload.get("payload", node.published)
    builder = get_archub_content_builder_service()
    builder_blocks = builder.parse_blocks(payload.get("builder_blocks"))
    response = _TEMPLATES.TemplateResponse(
        request,
        template_name,
        {
            "title": payload.get("seo_title") or payload.get("title") or node.name,
            **_seo_context(request, node, payload),
            "node": node,
            "content_type": content_type,
            "template": template,
            "domain": _request_domain_payload(request),
            "payload": payload,
            "culture": public_payload.get("culture", ""),
            "culture_fallback": public_payload.get("culture_fallback", False),
            "segment": public_payload.get("segment", ""),
            "segment_fallback": public_payload.get("segment_fallback", False),
            "builder_blocks": builder_blocks,
            "rendered_blocks": builder.render_blocks(builder_blocks),
            "children": [
                child
                for child in cms.published_children(node.node_id)
                if _can_read_public_content(request, child)
            ],
            "current_user": current_user(request),
        },
    )
    response.headers.update(cache_headers)
    return response
