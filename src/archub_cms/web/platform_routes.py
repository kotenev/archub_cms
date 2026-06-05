"""HTTP surface for the new platform capabilities: plugins + hybrid knowledge.

Kept in its own router (included alongside the legacy ``router``) so the
2.5k-line ``routes.py`` is left untouched. Endpoints are read-only JSON APIs
under ``/api/platform``.
"""

from __future__ import annotations

__all__ = ["platform_router"]

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from archub_cms.application.delivery_read_service import get_archub_delivery_read_service
from archub_cms.application.knowledge import (
    KnowledgeQuery,
    get_archub_knowledge_base_service,
)
from archub_cms.application.modeling_service import get_archub_modeling_query_service
from archub_cms.extensibility.host import get_plugin_host

platform_router = APIRouter(prefix="/api/platform", tags=["platform"])


def _knowledge_service():
    # Inject the loaded plugin host so search blends plugin-contributed hits.
    return get_archub_knowledge_base_service(plugin_host=get_plugin_host())


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
