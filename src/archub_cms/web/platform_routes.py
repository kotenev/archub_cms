"""HTTP surface for the new platform capabilities: plugins + hybrid knowledge.

Kept in its own router (included alongside the legacy ``router``) so the
2.5k-line ``routes.py`` is left untouched. Endpoints are read-only JSON APIs
under ``/api/platform``.
"""

from __future__ import annotations

__all__ = ["platform_router"]

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from archub_cms.application.activity_feed_service import get_archub_activity_feed_service
from archub_cms.application.agent_service import get_archub_agent_service
from archub_cms.application.ai_chat_service import get_archub_ai_chat_service
from archub_cms.application.analytics_service import get_archub_analytics_service
from archub_cms.application.audit_trail_service import get_archub_audit_trail_service
from archub_cms.application.blueprint_service import (
    BlueprintCommandService,
    BlueprintNotFoundError,
    get_archub_blueprint_query_service,
)
from archub_cms.application.bookmark_service import get_archub_bookmark_service
from archub_cms.application.comments_thread_service import get_archub_comments_thread_service
from archub_cms.application.custom_field_service import get_archub_custom_field_service
from archub_cms.application.dashboard_service import get_archub_dashboard_service
from archub_cms.application.delivery_read_service import get_archub_delivery_read_service
from archub_cms.application.embedding_store_service import get_archub_embedding_store_service
from archub_cms.application.fts_search_service import get_archub_fts_search_service
from archub_cms.application.governance_service import (
    AccessControlService,
    get_archub_governance_query_service,
)
from archub_cms.application.graph_service import get_archub_graph_service
from archub_cms.application.ingestion_service import get_archub_ingestion_service
from archub_cms.application.knowledge import (
    KnowledgeQuery,
    get_archub_knowledge_base_service,
)
from archub_cms.application.live_edit_service import get_archub_live_edit_service
from archub_cms.application.localization_service import (
    LocalizationCommandService,
    get_archub_localization_query_service,
)
from archub_cms.application.lock_service import (
    LockCommandService,
    LockConflictError,
    get_archub_lock_query_service,
)
from archub_cms.application.media_service import (
    MediaCommandService,
    StorageService,
    get_archub_media_query_service,
)
from archub_cms.application.modeling_service import get_archub_modeling_query_service
from archub_cms.application.notification_hub_service import get_archub_notification_hub_service
from archub_cms.application.packaging_service import get_archub_packaging_service
from archub_cms.application.page_cloning_service import get_archub_page_cloning_service
from archub_cms.application.pdf_export_service import get_archub_pdf_export_service
from archub_cms.application.permission_service import get_archub_permission_service
from archub_cms.application.platform import get_archub_platform
from archub_cms.application.plugin_management_service import (
    get_archub_plugin_management_service,
)
from archub_cms.application.revisions_diff_service import get_archub_revisions_diff_service
from archub_cms.application.runtime_service import (
    RuntimeCommandService,
    get_archub_runtime_query_service,
)
from archub_cms.application.scheduler_service import get_archub_scheduler_service
from archub_cms.application.search_service import get_archub_search_service
from archub_cms.application.space_service import get_archub_space_service
from archub_cms.application.subscription_service import (
    SubscriptionCommandService,
    get_archub_subscription_query_service,
)
from archub_cms.application.tag_service import get_archub_tag_service
from archub_cms.application.template_service import get_archub_template_service
from archub_cms.application.trash_service import (
    TrashCommandService,
    TrashItemNotFoundError,
    get_archub_trash_query_service,
)
from archub_cms.application.versioning_service import (
    VersioningCommandService,
    VersionNotFoundError,
    get_archub_versioning_query_service,
)
from archub_cms.application.webhooks_service import (
    WebhooksCommandService,
    get_archub_webhooks_query_service,
)
from archub_cms.application.workflow_service import (
    WorkflowCommandService,
    get_archub_workflow_query_service,
)
from archub_cms.domain.search.models import SearchQuery
from archub_cms.domain.workflow.workflow import WorkflowTransitionError
from archub_cms.extensibility.host import get_plugin_host

platform_router = APIRouter(prefix="/api/platform", tags=["platform"])


def _knowledge_service():
    # Inject the loaded plugin host so search blends plugin-contributed hits.
    return get_archub_knowledge_base_service(plugin_host=get_plugin_host())


def _dict_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


@platform_router.get("/capabilities")
def platform_capabilities() -> dict[str, Any]:
    return get_archub_platform(plugin_host=get_plugin_host()).capabilities()


@platform_router.get("/index")
def platform_index() -> dict[str, Any]:
    """Self-describing API browser: every platform route grouped by context."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for route in platform_router.routes:
        path = getattr(route, "path", "")
        methods = sorted(set(getattr(route, "methods", set())) - {"HEAD", "OPTIONS"})
        if not path.startswith("/api/platform"):
            continue
        rel = path.removeprefix("/api/platform/").removeprefix("/api/platform")
        section = rel.split("/", 1)[0] or "platform"
        groups.setdefault(section, []).append({"path": path, "methods": methods})
    for routes in groups.values():
        routes.sort(key=lambda r: r["path"])
    return {
        "sections": {name: groups[name] for name in sorted(groups)},
        "section_count": len(groups),
        "route_count": sum(len(routes) for routes in groups.values()),
    }


@platform_router.get("/report")
def platform_report() -> dict[str, Any]:
    service = _knowledge_service()
    report = service.platform_report()
    report["plugin_runtime"] = get_plugin_host().report()
    return report


@platform_router.get("/plugins")
def plugin_runtime() -> dict[str, Any]:
    return get_plugin_host().report()


@platform_router.get("/plugins/catalog")
def plugin_catalog() -> dict[str, Any]:
    return _knowledge_service().plugin_catalog()


@platform_router.get("/plugins/manage")
def plugin_manage() -> dict[str, Any]:
    return get_archub_plugin_management_service().catalog()


@platform_router.post("/plugins/{plugin_id}/enable")
def plugin_enable(
    plugin_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return get_archub_plugin_management_service().enable(
            plugin_id, actor=str(payload.get("actor") or "")
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@platform_router.post("/plugins/{plugin_id}/disable")
def plugin_disable(
    plugin_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return get_archub_plugin_management_service().disable(
            plugin_id, actor=str(payload.get("actor") or "")
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@platform_router.post("/plugins/{plugin_id}/settings")
def plugin_settings(
    plugin_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return get_archub_plugin_management_service().configure(
            plugin_id,
            dict(payload.get("settings") or {}),
            actor=str(payload.get("actor") or ""),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@platform_router.get("/search")
def federated_search(
    q: str = Query(default=""),
    content_types: str = Query(default=""),
    spaces: str = Query(default=""),
    tags: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    query = SearchQuery(
        q=q,
        content_types=_csv(content_types),
        spaces=_csv(spaces),
        tags=_csv(tags),
        limit=limit,
        offset=offset,
    )
    return get_archub_search_service(_knowledge_service()).search(query).as_dict()


@platform_router.post("/search")
def federated_search_post(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    return get_archub_search_service(_knowledge_service()).search_dict(payload)


@platform_router.get("/locks")
def locks_list(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
    return get_archub_lock_query_service().active_locks(limit=limit)


@platform_router.get("/locks/{node_id}")
def lock_detail(node_id: str) -> dict[str, Any]:
    found = get_archub_lock_query_service().lock(node_id)
    return found if found is not None else {"node_id": node_id, "locked": False}


@platform_router.post("/locks/{node_id}/acquire")
def lock_acquire(
    node_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return LockCommandService().acquire(
            node_id,
            owner=str(payload.get("owner") or ""),
            ttl_seconds=float(payload.get("ttl_seconds") or 1800.0),
            note=str(payload.get("note") or ""),
            force=bool(payload.get("force", False)),
        )
    except LockConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@platform_router.post("/locks/{node_id}/release")
def lock_release(
    node_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return LockCommandService().release(
            node_id, owner=str(payload.get("owner") or ""), force=bool(payload.get("force", False))
        )
    except LockConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@platform_router.get("/trash")
def trash_list(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_trash_query_service().items(limit=limit)


@platform_router.post("/trash/{node_id}/restore")
def trash_restore(
    node_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return TrashCommandService().restore(node_id, actor=str(payload.get("actor") or ""))
    except TrashItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"not in recycle bin: {exc}") from exc


@platform_router.delete("/trash/{node_id}")
def trash_purge(node_id: str, actor: str = Query(default="")) -> dict[str, Any]:
    try:
        return TrashCommandService().purge(node_id, actor=actor)
    except TrashItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"not in recycle bin: {exc}") from exc


@platform_router.post("/trash/empty")
def trash_empty(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    return TrashCommandService().empty(actor=str(payload.get("actor") or ""))


@platform_router.get("/blueprints")
def blueprints_list(
    content_type: str = Query(default=""), limit: int = Query(default=100, ge=1, le=1000)
) -> dict[str, Any]:
    return get_archub_blueprint_query_service().blueprints(
        content_type_alias=content_type, limit=limit
    )


@platform_router.get("/blueprints/{blueprint_id}")
def blueprint_detail(blueprint_id: str) -> dict[str, Any]:
    found = get_archub_blueprint_query_service().blueprint(blueprint_id)
    if found is None:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return found


@platform_router.post("/blueprints")
def blueprint_create(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        blueprint = BlueprintCommandService().create_blueprint(
            content_type_alias=str(payload.get("content_type_alias") or ""),
            name=str(payload.get("name") or ""),
            payload=_dict_payload(payload.get("payload")),
            description=str(payload.get("description") or ""),
            actor=str(payload.get("actor") or ""),
            blueprint_id=str(payload.get("blueprint_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return blueprint.as_dict()


@platform_router.post("/blueprints/{blueprint_id}/instantiate")
def blueprint_instantiate(
    blueprint_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return BlueprintCommandService().instantiate(
            blueprint_id,
            parent_id=str(payload.get("parent_id") or "root"),
            name=str(payload.get("name") or ""),
            overrides=_dict_payload(payload.get("overrides")),
            actor=str(payload.get("actor") or ""),
        )
    except BlueprintNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"blueprint not found: {exc}") from exc


@platform_router.get("/search/fts")
def fulltext_search(
    q: str = Query(default=""), limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    return get_archub_fts_search_service(knowledge=_knowledge_service()).search(q, limit=limit)


@platform_router.post("/search/fts/reindex")
def fulltext_reindex() -> dict[str, Any]:
    return get_archub_fts_search_service(knowledge=_knowledge_service()).reindex()


@platform_router.get("/knowledge/search")
def knowledge_search(
    q: str = Query(default=""),
    space_key: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    service = _knowledge_service()
    hits = service.hybrid_search(q, space_key=space_key, limit=limit)
    return {
        "query": q,
        "space_key": space_key,
        "items": [hit.as_dict() for hit in hits],
        "total": len(hits),
    }


@platform_router.post("/knowledge/agent-answer")
def knowledge_agent_answer(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    agent = get_archub_agent_service(plugin_host=get_plugin_host())
    return agent.answer(
        str(payload.get("question") or ""),
        tools=tuple(payload.get("tools") or ()),
        auto=bool(payload.get("auto", False)),
        space_key=str(payload.get("space_key") or ""),
        corpus_key=str(payload.get("corpus_key") or ""),
        limit=int(payload.get("limit") or 5),
    )


@platform_router.get("/knowledge/tools")
def knowledge_tools() -> dict[str, Any]:
    tools = get_archub_agent_service(plugin_host=get_plugin_host()).available_tools()
    return {"tools": tools, "total": len(tools)}


@platform_router.get("/knowledge/graph")
def knowledge_graph(
    space_key: str = Query(default=""), limit: int = Query(default=200)
) -> dict[str, Any]:
    return _knowledge_service().graph(space_key=space_key, limit=limit).as_dict()


@platform_router.get("/analytics/dashboard")
def analytics_dashboard() -> dict[str, Any]:
    return get_archub_analytics_service().dashboard()


@platform_router.get("/analytics/health")
def analytics_health() -> dict[str, Any]:
    return get_archub_analytics_service().health()


@platform_router.get("/analytics/stats")
def analytics_stats() -> dict[str, int]:
    return get_archub_analytics_service().stats()


@platform_router.get("/analytics/audit")
def analytics_audit() -> dict[str, Any]:
    return get_archub_analytics_service().audit()


@platform_router.get("/analytics/cache")
def analytics_cache(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    return get_archub_analytics_service().cache(limit=limit)


@platform_router.get("/analytics/activity")
def analytics_activity(
    node_id: str = Query(default=""),
    action: str = Query(default=""),
    actor: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    return get_archub_analytics_service().activity(
        node_id=node_id, action=action, actor=actor, limit=limit
    )


@platform_router.get("/graph/overview")
def graph_overview(
    space_key: str = Query(default=""), limit: int = Query(default=200, ge=1, le=1000)
) -> dict[str, Any]:
    return get_archub_graph_service().overview(space_key=space_key, limit=limit)


@platform_router.get("/graph/backlinks")
def graph_backlinks(route: str = Query(...), space_key: str = Query(default="")) -> dict[str, Any]:
    return get_archub_graph_service().backlinks(route, space_key=space_key)


@platform_router.get("/graph/backlinks-index")
def graph_backlinks_index(space_key: str = Query(default="")) -> dict[str, Any]:
    return get_archub_graph_service().backlinks_index(space_key=space_key)


@platform_router.get("/graph/canvas")
def graph_canvas(
    space_key: str = Query(default=""), limit: int = Query(default=200, ge=1, le=1000)
) -> dict[str, Any]:
    return get_archub_graph_service().canvas(space_key=space_key, limit=limit)


@platform_router.get("/knowledge/documents")
def knowledge_documents(
    q: str = Query(default=""),
    space_key: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=500),
) -> dict[str, Any]:
    service = _knowledge_service()
    return service.documents(KnowledgeQuery(q=q, space_key=space_key, limit=limit))


@platform_router.post("/knowledge/answer")
def knowledge_answer(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    service = _knowledge_service()
    answer = service.answer(
        str(payload.get("question") or ""),
        space_key=str(payload.get("space_key") or ""),
        corpus_key=str(payload.get("corpus_key") or ""),
        limit=int(payload.get("limit") or 5),
    )
    return answer.as_dict()


# -- executable extension points (renderers/macros/importers/exporters/tools) --


@platform_router.post("/render")
def render_content(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    rendered = get_plugin_host().render(
        str(payload.get("body") or ""), context=payload.get("context") or {}
    )
    return {"rendered": rendered}


@platform_router.get("/extensions")
def list_extensions() -> dict[str, Any]:
    host = get_plugin_host()
    report = host.report()
    return {
        "macros": report["macros"],
        "renderers": report["renderers"],
        "importers": report["importers"],
        "exporters": report["exporters"],
        "llm_tools": report["llm_tools"],
        "search_extensions": report["search_extensions"],
        "event_hooks": report["event_hooks"],
    }


@platform_router.post("/ingest/markdown")
def ingest_markdown(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    service = get_archub_ingestion_service(plugin_host=get_plugin_host())
    try:
        return service.import_markdown(
            payload.get("source"),
            importer=str(payload.get("importer") or "markdown"),
            parent_id=str(payload.get("parent_id") or "root"),
            content_type_alias=str(payload.get("content_type") or "page"),
            publish=bool(payload.get("publish", False)),
            actor=str(payload.get("actor") or "system"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@platform_router.post("/import/{importer}")
def import_documents(
    importer: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        documents = get_plugin_host().import_documents(importer, payload.get("source"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"importer": importer, "documents": documents, "total": len(documents)}


@platform_router.post("/export/{exporter}")
def export_documents(
    exporter: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> Any:
    try:
        return get_plugin_host().export_documents(exporter, payload.get("documents") or [])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@platform_router.post("/tools/{name}/run")
def run_tool(
    name: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        result = get_plugin_host().run_tool(name, payload.get("arguments") or payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tool": name, "result": result}


# -- modeling context (content types / data types / templates) ----------------


@platform_router.get("/modeling/report")
def modeling_report() -> dict[str, Any]:
    return get_archub_modeling_query_service().report()


@platform_router.get("/modeling/content-types")
def modeling_content_types() -> dict[str, Any]:
    return get_archub_modeling_query_service().content_types()


@platform_router.get("/modeling/content-types/{alias}")
def modeling_content_type(alias: str) -> dict[str, Any]:
    found = get_archub_modeling_query_service().content_type(alias)
    if found is None:
        raise HTTPException(status_code=404, detail="content type not found")
    return found


@platform_router.get("/modeling/data-types")
def modeling_data_types(limit: int = Query(default=200, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_modeling_query_service().data_types(limit=limit)


@platform_router.get("/modeling/templates")
def modeling_templates(limit: int = Query(default=200, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_modeling_query_service().templates(limit=limit)


# -- delivery context (sitemap / feed / tags / redirects) ---------------------


@platform_router.get("/delivery/sitemap")
def delivery_sitemap(base_url: str = Query(default="")) -> dict[str, Any]:
    return get_archub_delivery_read_service().sitemap(base_url=base_url)


@platform_router.get("/delivery/feed")
def delivery_feed(
    base_url: str = Query(default=""), limit: int = Query(default=25, ge=1, le=100)
) -> dict[str, Any]:
    return get_archub_delivery_read_service().feed(base_url=base_url, limit=limit)


@platform_router.get("/delivery/tags")
def delivery_tags() -> dict[str, Any]:
    return get_archub_delivery_read_service().tags()


@platform_router.get("/delivery/tags/{tag}")
def delivery_by_tag(tag: str, limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return get_archub_delivery_read_service().by_tag(tag, limit=limit)


@platform_router.get("/delivery/redirects")
def delivery_redirects(active_only: bool = Query(default=False)) -> dict[str, Any]:
    return get_archub_delivery_read_service().redirects(active_only=active_only)


@platform_router.get("/delivery/resolve")
def delivery_resolve(path: str = Query(...)) -> dict[str, Any]:
    found = get_archub_delivery_read_service().resolve(path)
    if found is None:
        raise HTTPException(status_code=404, detail="no redirect for path")
    return found


# -- versioning context (history / diff / restore) ----------------------------


@platform_router.get("/versioning/{node_id}/history")
def versioning_history(
    node_id: str, limit: int = Query(default=20, ge=1, le=500)
) -> dict[str, Any]:
    return get_archub_versioning_query_service().history(node_id, limit=limit)


@platform_router.get("/versioning/{node_id}/diff")
def versioning_diff(
    node_id: str,
    from_version: int = Query(..., alias="from", ge=1),
    to_version: int = Query(..., alias="to", ge=1),
) -> dict[str, Any]:
    try:
        return get_archub_versioning_query_service().diff(
            node_id, from_version_no=from_version, to_version_no=to_version
        )
    except VersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"version not found: {exc}") from exc


@platform_router.post("/versioning/{node_id}/restore")
def versioning_restore(
    node_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return VersioningCommandService().restore(
            node_id, int(payload.get("version_no") or 0), actor=str(payload.get("actor") or "")
        )
    except VersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"version not found: {exc}") from exc


# -- governance context (RBAC + public access + pluggable auth) ---------------


@platform_router.get("/governance/actions")
def governance_actions() -> dict[str, Any]:
    q = get_archub_governance_query_service()
    return {"actions": q.actions(), "policies": q.policies()}


@platform_router.get("/governance/permissions")
def governance_permissions(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_governance_query_service().permissions(limit=limit)


@platform_router.get("/governance/access-rules")
def governance_access_rules(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_governance_query_service().access_rules(limit=limit)


@platform_router.post("/governance/check")
def governance_check(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    acl = AccessControlService()
    allowed = acl.can_perform(
        username=str(payload.get("username") or ""),
        is_admin=bool(payload.get("is_admin")),
        action=str(payload.get("action") or "browse"),
        node_id=str(payload.get("node_id") or ""),
    )
    return {"allowed": allowed}


@platform_router.post("/governance/access-check")
def governance_access_check(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    acl = AccessControlService()
    return acl.can_access(
        str(payload.get("node_id") or ""),
        authenticated=bool(payload.get("authenticated")),
        groups=payload.get("groups") or [],
    )


@platform_router.get("/governance/whoami")
def governance_whoami(request: Request) -> dict[str, Any]:
    acl = AccessControlService(plugin_host=get_plugin_host())
    identity = acl.identity(request)
    if identity is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": getattr(identity, "username", ""),
        "is_admin": getattr(identity, "is_admin", False),
        "groups": list(getattr(identity, "groups", ())),
    }


# -- workflow context (review/approval state machine) -------------------------


@platform_router.get("/workflow/report")
def workflow_report(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    return get_archub_workflow_query_service().report(limit=limit)


@platform_router.get("/workflow/{node_id}")
def workflow_state(node_id: str) -> dict[str, Any]:
    return get_archub_workflow_query_service().get(node_id)


@platform_router.get("/workflow/{node_id}/transitions")
def workflow_transitions(node_id: str) -> dict[str, Any]:
    return get_archub_workflow_query_service().allowed_transitions(node_id)


@platform_router.post("/workflow/{node_id}/transition")
def workflow_transition(
    node_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        workflow = WorkflowCommandService().transition(
            node_id,
            str(payload.get("to") or ""),
            actor=str(payload.get("actor") or ""),
            note=str(payload.get("note") or ""),
            assigned_to=payload.get("assigned_to"),
        )
    except WorkflowTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return workflow.as_dict()


# -- media context + pluggable blob storage -----------------------------------


@platform_router.get("/media")
def media_assets(
    folder: str = Query(default=""), limit: int = Query(default=100, ge=1, le=500)
) -> dict[str, Any]:
    return get_archub_media_query_service().assets(folder=folder, limit=limit)


@platform_router.get("/media/folders")
def media_folders() -> dict[str, Any]:
    return get_archub_media_query_service().folders()


@platform_router.post("/media/register")
def media_register(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        asset = MediaCommandService().register(
            filename=str(payload.get("filename") or ""),
            content_type=str(payload.get("content_type") or ""),
            url=str(payload.get("url") or ""),
            original_name=str(payload.get("original_name") or ""),
            folder=str(payload.get("folder") or ""),
            alt_text=str(payload.get("alt_text") or ""),
            tags=payload.get("tags") or [],
            metadata=payload.get("metadata") or {},
            created_by=str(payload.get("created_by") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return asset.as_dict()


@platform_router.get("/storage")
def storage_backends() -> dict[str, Any]:
    backends = StorageService(plugin_host=get_plugin_host()).backends()
    return {"backends": backends, "total": len(backends)}


@platform_router.post("/storage/{backend}/put")
def storage_put(
    backend: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    service = StorageService(plugin_host=get_plugin_host())
    try:
        return service.put(
            backend, str(payload.get("key") or ""), str(payload.get("content") or "").encode()
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@platform_router.get("/storage/{backend}/get")
def storage_get(backend: str, key: str = Query(...)) -> dict[str, Any]:
    service = StorageService(plugin_host=get_plugin_host())
    try:
        data = service.get(backend, key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"backend": backend, "key": key, "content": data.decode("utf-8", errors="replace")}


# -- packaging context (portable content bundles) -----------------------------


@platform_router.post("/packaging/export")
def packaging_export(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    package = get_archub_packaging_service().export(
        name=str(payload.get("name") or "ArcHub package"),
        description=str(payload.get("description") or ""),
        node_ids=payload.get("node_ids") or [],
        include_descendants=bool(payload.get("include_descendants", True)),
        actor=str(payload.get("actor") or ""),
    )
    return {"summary": package.as_dict(), "package": package.data}


@platform_router.post("/packaging/inspect")
def packaging_inspect(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    package = _dict_payload(payload.get("package")) or payload
    return get_archub_packaging_service().inspect(package).as_dict()


@platform_router.post("/packaging/plan")
def packaging_plan(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    package = _dict_payload(payload.get("package")) or payload
    return get_archub_packaging_service().plan(
        package, overwrite=bool(payload.get("overwrite", False))
    )


@platform_router.post("/packaging/import")
def packaging_import(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    package = _dict_payload(payload.get("package"))
    try:
        return get_archub_packaging_service().import_package(
            package,
            actor=str(payload.get("actor") or ""),
            overwrite=bool(payload.get("overwrite", False)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# -- runtime / RAG-export context ---------------------------------------------


@platform_router.get("/runtime/snapshot")
def runtime_snapshot() -> dict[str, Any]:
    return get_archub_runtime_query_service().snapshot()


@platform_router.get("/runtime/status")
def runtime_status() -> dict[str, Any]:
    return get_archub_runtime_query_service().status()


@platform_router.get("/runtime/search")
def runtime_search(
    corpus: str = Query(default=""),
    q: str = Query(default=""),
    limit: int = Query(default=6, ge=1, le=50),
) -> dict[str, Any]:
    return get_archub_runtime_query_service().search(corpus, q, limit=limit)


@platform_router.post("/runtime/export")
def runtime_export(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    return RuntimeCommandService().export(actor=str(payload.get("actor") or "system"))


@platform_router.post("/runtime/rebuild-index")
def runtime_rebuild_index(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    return RuntimeCommandService().rebuild_indexes(
        corpus_key=payload.get("corpus_key"),
        model=payload.get("model"),
        actor=str(payload.get("actor") or "system"),
    )


# -- localization / i18n context ----------------------------------------------


@platform_router.get("/localization/dictionary")
def localization_dictionary(
    group: str = Query(default=""), limit: int = Query(default=200, ge=1, le=500)
) -> dict[str, Any]:
    return get_archub_localization_query_service().dictionary(group=group, limit=limit)


@platform_router.get("/localization/translate")
def localization_translate(
    key: str = Query(...),
    culture: str = Query(default=""),
    group: str = Query(default=""),
    default: str = Query(default=""),
) -> dict[str, Any]:
    return get_archub_localization_query_service().translate(
        key, culture=culture, group=group, default=default
    )


@platform_router.post("/localization/dictionary")
def localization_dictionary_upsert(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return LocalizationCommandService().upsert_dictionary(
            key=str(payload.get("key") or ""),
            group=str(payload.get("group") or ""),
            values=_dict_payload(payload.get("values")),
            actor=str(payload.get("actor") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@platform_router.get("/localization/{node_id}/variants")
def localization_variants(node_id: str) -> dict[str, Any]:
    return get_archub_localization_query_service().variants(node_id)


@platform_router.get("/localization/{node_id}/cultures")
def localization_cultures(node_id: str) -> dict[str, Any]:
    return get_archub_localization_query_service().cultures(node_id)


@platform_router.post("/localization/{node_id}/variants")
def localization_variant_upsert(
    node_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return LocalizationCommandService().upsert_variant(
            node_id,
            culture=str(payload.get("culture") or ""),
            payload=_dict_payload(payload.get("payload")),
            actor=str(payload.get("actor") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@platform_router.post("/localization/{node_id}/variants/{culture}/publish")
def localization_variant_publish(
    node_id: str,
    culture: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        return LocalizationCommandService().publish_variant(
            node_id, culture=culture, actor=str(payload.get("actor") or "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# -- webhooks / notifications context (Outbox) --------------------------------


@platform_router.get("/webhooks")
def webhooks_list(
    active_only: bool = Query(default=False), limit: int = Query(default=100, ge=1, le=500)
) -> dict[str, Any]:
    return get_archub_webhooks_query_service().webhooks(active_only=active_only, limit=limit)


@platform_router.get("/webhooks/deliveries")
def webhooks_deliveries(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_webhooks_query_service().deliveries(limit=limit)


@platform_router.get("/webhooks/report")
def webhooks_report(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return get_archub_webhooks_query_service().report(limit=limit)


@platform_router.get("/webhooks/matching")
def webhooks_matching(event_type: str = Query(...)) -> dict[str, Any]:
    return get_archub_webhooks_query_service().matching(event_type)


@platform_router.post("/webhooks")
def webhooks_upsert(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        webhook = WebhooksCommandService().upsert_webhook(
            name=str(payload.get("name") or ""),
            target_url=str(payload.get("target_url") or ""),
            events=payload.get("events") or [],
            secret=str(payload.get("secret") or ""),
            active=bool(payload.get("active", True)),
            actor=str(payload.get("actor") or ""),
            webhook_id=str(payload.get("webhook_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return webhook.as_dict()


@platform_router.post("/webhooks/dispatch")
def webhooks_dispatch(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    return WebhooksCommandService().dispatch(limit=int(payload.get("limit") or 50))


@platform_router.get("/notifications/channels")
def notification_channels() -> dict[str, Any]:
    channels = sorted(get_plugin_host().notification_channels)
    return {"channels": channels, "total": len(channels)}


# -- subscriptions / watchers (Confluence "watch") ----------------------------


@platform_router.post("/subscriptions/watch")
def subscriptions_watch(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 - FastAPI body marker
) -> dict[str, Any]:
    try:
        sub = SubscriptionCommandService().watch(
            subscriber=str(payload.get("subscriber") or ""),
            node_id=str(payload.get("node_id") or ""),
            event_prefix=str(payload.get("event_prefix") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return sub.as_dict()


@platform_router.delete("/subscriptions/{subscription_id}")
def subscriptions_unwatch(subscription_id: str, actor: str = Query(default="")) -> dict[str, Any]:
    return {"removed": SubscriptionCommandService().unwatch(subscription_id, actor=actor)}


@platform_router.get("/subscriptions")
def subscriptions_list(subscriber: str = Query(...)) -> dict[str, Any]:
    return get_archub_subscription_query_service().subscriptions_for(subscriber)


@platform_router.get("/subscriptions/inbox")
def subscriptions_inbox(
    subscriber: str = Query(...), limit: int = Query(default=50, ge=1, le=500)
) -> dict[str, Any]:
    return get_archub_subscription_query_service().inbox(subscriber, limit=limit)


@platform_router.get("/subscriptions/watchers/{node_id}")
def subscriptions_watchers(node_id: str) -> dict[str, Any]:
    return get_archub_subscription_query_service().watchers_of(node_id)


# -- scheduler (cron-like jobs) ------------------------------------------------


@platform_router.get("/scheduler/jobs")
def scheduler_list_jobs() -> dict[str, Any]:
    jobs = get_archub_scheduler_service().list_jobs()
    return {"jobs": jobs, "total": len(jobs)}


@platform_router.post("/scheduler/tick")
def scheduler_tick() -> dict[str, Any]:
    return get_archub_scheduler_service().tick()


# -- audit trail (immutable log) -----------------------------------------------


@platform_router.get("/audit-trail")
def audit_trail_query(
    aggregate_id: str = Query(default=""),
    actor: str = Query(default=""),
    action: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    from archub_cms.domain.audit_trail.entry import AuditQuery

    return get_archub_audit_trail_service().query(
        AuditQuery(aggregate_id=aggregate_id, actor=actor, action=action, limit=limit)
    )


@platform_router.get("/audit-trail/{aggregate_id}")
def audit_trail_for_aggregate(aggregate_id: str, limit: int = Query(default=50)) -> dict[str, Any]:
    return get_archub_audit_trail_service().for_aggregate(aggregate_id, limit=limit)


# -- notification hub ----------------------------------------------------------


@platform_router.get("/notifications/inbox")
def notification_inbox(
    username: str = Query(...),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    return get_archub_notification_hub_service().inbox(
        username, unread_only=unread_only, limit=limit
    )


@platform_router.post("/notifications/{notification_id}/read")
def notification_mark_read(notification_id: str) -> dict[str, Any]:
    return {"read": get_archub_notification_hub_service().mark_read(notification_id)}


@platform_router.get("/notifications/preferences/{username}")
def notification_preferences(username: str) -> dict[str, Any]:
    return get_archub_notification_hub_service().preferences(username)


# -- bookmarks / favorites -----------------------------------------------------


@platform_router.post("/bookmarks")
def bookmarks_add(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    return get_archub_bookmark_service().add(
        username=str(payload.get("username") or ""),
        node_id=str(payload.get("node_id") or ""),
        folder_id=str(payload.get("folder_id") or ""),
        note=str(payload.get("note") or ""),
    )


@platform_router.delete("/bookmarks/{bookmark_id}")
def bookmarks_remove(bookmark_id: str) -> dict[str, Any]:
    return {"removed": get_archub_bookmark_service().remove(bookmark_id)}


@platform_router.get("/bookmarks")
def bookmarks_list(
    username: str = Query(...), folder_id: str = Query(default="")
) -> dict[str, Any]:
    return get_archub_bookmark_service().list_for_user(username, folder_id=folder_id)


@platform_router.get("/bookmarks/folders")
def bookmarks_folders(username: str = Query(...)) -> dict[str, Any]:
    return get_archub_bookmark_service().folders(username)


@platform_router.post("/bookmarks/folders")
def bookmarks_create_folder(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    return get_archub_bookmark_service().create_folder(
        username=str(payload.get("username") or ""),
        name=str(payload.get("name") or ""),
        parent_folder_id=str(payload.get("parent_folder_id") or ""),
    )


# -- tags / taxonomy -----------------------------------------------------------


@platform_router.get("/tags")
def tags_list() -> dict[str, Any]:
    return get_archub_tag_service().list_all()


@platform_router.get("/tags/tree")
def tags_tree() -> dict[str, Any]:
    return get_archub_tag_service().tree()


@platform_router.post("/tags")
def tags_upsert(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    from archub_cms.domain.tags.tag import Tag

    tag = Tag(
        slug=str(payload.get("slug") or ""),
        display_name=str(payload.get("display_name") or ""),
        parent_slug=str(payload.get("parent_slug") or ""),
        aliases=tuple(payload.get("aliases") or ()),
        description=str(payload.get("description") or ""),
    )
    return get_archub_tag_service().upsert(tag)


@platform_router.delete("/tags/{slug}")
def tags_delete(slug: str) -> dict[str, Any]:
    return {"removed": get_archub_tag_service().delete(slug)}


# -- spaces (Confluence-style) -------------------------------------------------


@platform_router.get("/spaces")
def spaces_list() -> dict[str, Any]:
    return get_archub_space_service().list_all()


@platform_router.get("/spaces/{space_key}")
def spaces_get(space_key: str) -> dict[str, Any]:
    result = get_archub_space_service().get(space_key)
    if result is None:
        raise HTTPException(status_code=404, detail="space not found")
    return result


@platform_router.post("/spaces")
def spaces_upsert(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    from archub_cms.domain.spaces.space import Space, SpaceSettings

    settings_data = payload.get("settings") or {}
    settings = SpaceSettings(
        icon=str(settings_data.get("icon") or ""),
        color=str(settings_data.get("color") or "#0B7285"),
        default_content_type=str(settings_data.get("default_content_type") or "page"),
        allow_comments=bool(settings_data.get("allow_comments", True)),
        allow_reactions=bool(settings_data.get("allow_reactions", True)),
        theme=str(settings_data.get("theme") or "default"),
        custom_styles=str(settings_data.get("custom_styles") or ""),
        sidebar_items=tuple(settings_data.get("sidebar_items") or ()),
    )
    space = Space(
        space_key=str(payload.get("space_key") or ""),
        name=str(payload.get("name") or ""),
        description=str(payload.get("description") or ""),
        root_node_id=str(payload.get("root_node_id") or ""),
        owner=str(payload.get("owner") or ""),
        visibility=str(payload.get("visibility") or "public"),
        settings=settings,
    )
    return get_archub_space_service().upsert(space)


@platform_router.delete("/spaces/{space_key}")
def spaces_delete(space_key: str) -> dict[str, Any]:
    return {"removed": get_archub_space_service().delete(space_key)}


# -- comments thread -----------------------------------------------------------


@platform_router.get("/comments/threads/{node_id}")
def comment_threads_list(node_id: str) -> dict[str, Any]:
    return get_archub_comments_thread_service().list_for_node(node_id)


@platform_router.post("/comments/threads")
def comment_threads_create(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    thread = get_archub_comments_thread_service().create_thread(
        node_id=str(payload.get("node_id") or ""),
        title=str(payload.get("title") or ""),
    )
    return {"thread_id": thread.thread_id, "node_id": thread.node_id}


@platform_router.post("/comments")
def comments_add(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    comment = get_archub_comments_thread_service().add_comment(
        thread_id=str(payload.get("thread_id") or ""),
        author=str(payload.get("author") or ""),
        body=str(payload.get("body") or ""),
        parent_id=str(payload.get("parent_comment_id") or ""),
    )
    return comment.as_dict()


# -- templates -----------------------------------------------------------------


@platform_router.get("/templates")
def templates_list(space_key: str = "", category: str = "") -> dict[str, Any]:
    return get_archub_template_service().list_templates(space_key=space_key, category=category)


@platform_router.get("/templates/{template_id}")
def templates_get(template_id: str) -> dict[str, Any]:
    tmpl = get_archub_template_service().get_template(template_id)
    if tmpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    return tmpl.as_dict()


@platform_router.post("/templates")
def templates_create(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    tmpl = get_archub_template_service().create_template(
        name=str(payload.get("name") or ""),
        body=str(payload.get("body") or ""),
        category=str(payload.get("category") or "blank"),
        space_key=str(payload.get("space_key") or ""),
        created_by=str(payload.get("created_by") or ""),
    )
    return tmpl.as_dict()


# -- permissions ---------------------------------------------------------------


@platform_router.get("/permissions")
def permissions_list(resource_type: str, resource_id: str) -> dict[str, Any]:
    return get_archub_permission_service().list_permissions_for_resource(resource_type, resource_id)


@platform_router.post("/permissions")
def permissions_grant(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    perm = get_archub_permission_service().grant(
        subject_type=str(payload.get("subject_type") or ""),
        subject_id=str(payload.get("subject_id") or ""),
        resource_type=str(payload.get("resource_type") or ""),
        resource_id=str(payload.get("resource_id") or ""),
        level=str(payload.get("level") or "view"),
        granted_by=str(payload.get("granted_by") or ""),
    )
    return perm.as_dict()


@platform_router.get("/permissions/check")
def permissions_check(
    user: str, resource_type: str, resource_id: str, level: str = "view"
) -> dict[str, Any]:
    return get_archub_permission_service().check_access(user, resource_type, resource_id, level)


# -- ai chat -------------------------------------------------------------------


@platform_router.get("/chat/conversations")
def chat_conversations_list(owner: str) -> dict[str, Any]:
    return get_archub_ai_chat_service().list_conversations(owner)


@platform_router.post("/chat/conversations")
def chat_conversations_create(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    conv = get_archub_ai_chat_service().create_conversation(
        title=str(payload.get("title") or "New Chat"),
        owner=str(payload.get("owner") or ""),
        space_key=str(payload.get("space_key") or ""),
    )
    return conv.as_dict()


@platform_router.post("/chat/send")
def chat_send(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    return get_archub_ai_chat_service().send_message(
        conversation_id=str(payload.get("conversation_id") or ""),
        message=str(payload.get("message") or ""),
        user=str(payload.get("user") or ""),
    )


# -- dashboard -----------------------------------------------------------------


@platform_router.get("/dashboard")
def dashboard_get(owner: str, space_key: str = "") -> dict[str, Any]:
    return get_archub_dashboard_service().get_layout(owner, space_key)


@platform_router.post("/dashboard/widgets")
def dashboard_add_widget(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    widget = get_archub_dashboard_service().add_widget(
        layout_id=str(payload.get("layout_id") or ""),
        widget_type=str(payload.get("widget_type") or "recent_pages"),
        title=str(payload.get("title") or ""),
        config=payload.get("config") or {},
    )
    return widget.as_dict()


# -- activity feed -------------------------------------------------------------


@platform_router.get("/activity")
def activity_feed_list(space_key: str = "", actor: str = "", limit: int = 50) -> dict[str, Any]:
    return get_archub_activity_feed_service().list_activities(
        space_key=space_key, actor=actor, limit=limit
    )


@platform_router.get("/activity/user/{username}")
def activity_feed_user(username: str, limit: int = 50) -> dict[str, Any]:
    return get_archub_activity_feed_service().list_user_activities(username, limit)


# -- custom fields -------------------------------------------------------------


@platform_router.get("/custom-fields/definitions")
def custom_fields_list(space_key: str = "") -> dict[str, Any]:
    return get_archub_custom_field_service().list_field_definitions(space_key)


@platform_router.post("/custom-fields/definitions")
def custom_fields_define(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    definition = get_archub_custom_field_service().define_field(
        name=str(payload.get("name") or ""),
        field_type=str(payload.get("field_type") or "text"),
        space_key=str(payload.get("space_key") or ""),
        description=str(payload.get("description") or ""),
        required=bool(payload.get("required")),
        options=tuple(payload.get("options") or ()),
    )
    return definition.as_dict()


@platform_router.get("/custom-fields/values/{node_id}")
def custom_fields_get_values(node_id: str) -> dict[str, Any]:
    return get_archub_custom_field_service().get_field_values(node_id)


# -- page cloning --------------------------------------------------------------


@platform_router.post("/pages/clone")
def pages_clone(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    from archub_cms.domain.page_cloning.models import CloneOptions

    options = CloneOptions(
        source_id=str(payload.get("source_id") or ""),
        target_parent_id=str(payload.get("target_parent_id") or ""),
        target_space_key=str(payload.get("target_space_key") or ""),
        clone_children=bool(payload.get("clone_children", True)),
        clone_attachments=bool(payload.get("clone_attachments", True)),
        clone_custom_fields=bool(payload.get("clone_custom_fields", True)),
        clone_comments=bool(payload.get("clone_comments", False)),
        title_prefix=str(payload.get("title_prefix") or "Copy of "),
        owner=str(payload.get("owner") or ""),
    )
    result = get_archub_page_cloning_service().clone_page(options)
    return result.as_dict()


@platform_router.post("/pages/clone/estimate")
def pages_clone_estimate(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    return get_archub_page_cloning_service().estimate_clone(
        source_id=str(payload.get("source_id") or ""),
        include_children=bool(payload.get("include_children", True)),
    )


# -- pdf/export ----------------------------------------------------------------


@platform_router.get("/export/formats")
def export_formats_list() -> dict[str, Any]:
    return get_archub_pdf_export_service().get_supported_formats()


@platform_router.post("/export/jobs")
def export_jobs_create(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    job = get_archub_pdf_export_service().create_export_job(
        format=str(payload.get("format") or "pdf"),
        target_type=str(payload.get("target_type") or "page"),
        target_id=str(payload.get("target_id") or ""),
        requester=str(payload.get("requester") or ""),
        options=payload.get("options"),
    )
    return job.as_dict()


@platform_router.get("/export/jobs")
def export_jobs_list(requester: str, limit: int = 20) -> dict[str, Any]:
    return get_archub_pdf_export_service().list_jobs(requester, limit)


@platform_router.get("/export/jobs/{job_id}")
def export_jobs_get(job_id: str) -> dict[str, Any]:
    return get_archub_pdf_export_service().get_job_status(job_id)


# -- embedding store ------------------------------------------------------------


@platform_router.get("/embeddings/stats")
def embeddings_stats() -> dict[str, Any]:
    return get_archub_embedding_store_service().stats()


@platform_router.get("/embeddings/stale")
def embeddings_stale(limit: int = 100) -> dict[str, Any]:
    return get_archub_embedding_store_service().list_stale(limit)


# -- revisions diff -------------------------------------------------------------


@platform_router.get("/revisions/diff")
def revisions_diff(node_id: str, old_revision: int, new_revision: int) -> dict[str, Any]:
    old_content = (
        get_archub_revisions_diff_service().get_revision_content(node_id, old_revision) or ""
    )
    new_content = (
        get_archub_revisions_diff_service().get_revision_content(node_id, new_revision) or ""
    )
    comparison = get_archub_revisions_diff_service().compare(
        node_id, old_content, new_content, old_revision, new_revision
    )
    return comparison.as_dict()


# -- live edit -----------------------------------------------------------------


@platform_router.post("/live-edit/sessions")
def live_edit_create_session(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    session = get_archub_live_edit_service().create_session(
        node_id=str(payload.get("node_id") or "")
    )
    return session.as_dict()


@platform_router.post("/live-edit/join")
def live_edit_join(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    presence = get_archub_live_edit_service().join_session(
        session_id=str(payload.get("session_id") or ""),
        user=str(payload.get("user") or ""),
        color=str(payload.get("color") or ""),
    )
    return presence.as_dict()


@platform_router.post("/live-edit/leave")
def live_edit_leave(
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    get_archub_live_edit_service().leave_session(
        session_id=str(payload.get("session_id") or ""),
        user=str(payload.get("user") or ""),
    )
    return {"left": True}


@platform_router.get("/live-edit/sessions/{session_id}/users")
def live_edit_users(session_id: str) -> dict[str, Any]:
    return get_archub_live_edit_service().get_active_users(session_id)


# -- health check --------------------------------------------------------------


@platform_router.get("/health")
def health_check() -> dict[str, Any]:
    from archub_cms.kernel.health_check import get_health_check_service

    return get_health_check_service().check()
