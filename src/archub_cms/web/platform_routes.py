"""HTTP surface for the new platform capabilities: plugins + hybrid knowledge.

Kept in its own router (included alongside the legacy ``router``) so the
2.5k-line ``routes.py`` is left untouched. Endpoints are read-only JSON APIs
under ``/api/platform``.
"""

from __future__ import annotations

__all__ = ["platform_router"]

from typing import Any

from fastapi import APIRouter, Body, Query

from archub_cms.application.knowledge import (
    KnowledgeQuery,
    get_archub_knowledge_base_service,
)
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
