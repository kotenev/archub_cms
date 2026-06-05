"""HTTP surface for the new platform capabilities: plugins + hybrid knowledge.

Kept in its own router (included alongside the legacy ``router``) so the
2.5k-line ``routes.py`` is left untouched. Endpoints are read-only JSON APIs
under ``/api/platform``.
"""

from __future__ import annotations

__all__ = ["platform_router"]

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from archub_cms.application.analytics_service import get_archub_analytics_service
from archub_cms.application.delivery_read_service import get_archub_delivery_read_service
from archub_cms.application.governance_service import (
    AccessControlService,
    get_archub_governance_query_service,
)
from archub_cms.application.graph_service import get_archub_graph_service
from archub_cms.application.knowledge import (
    KnowledgeQuery,
    get_archub_knowledge_base_service,
)
from archub_cms.application.localization_service import (
    LocalizationCommandService,
    get_archub_localization_query_service,
)
from archub_cms.application.media_service import (
    MediaCommandService,
    StorageService,
    get_archub_media_query_service,
)
from archub_cms.application.modeling_service import get_archub_modeling_query_service
from archub_cms.application.packaging_service import get_archub_packaging_service
from archub_cms.application.plugin_management_service import (
    get_archub_plugin_management_service,
)
from archub_cms.application.runtime_service import (
    RuntimeCommandService,
    get_archub_runtime_query_service,
)
from archub_cms.application.search_service import get_archub_search_service
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
