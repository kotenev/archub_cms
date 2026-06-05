"""HTTP surface for the collaboration context: comments, mentions, reactions.

Read/write JSON endpoints under ``/api/platform/collaboration``. Kept in its own
router (included by ``create_archub_app``) so the legacy ``routes.py`` is
untouched. The notifications feed is read from the bundled notifications plugin
via the plugin host, demonstrating the platform serving plugin-produced data.
"""

from __future__ import annotations

__all__ = ["collaboration_router"]

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from archub_cms.application.collaboration_service import (
    CommentNotFoundError,
    get_archub_collaboration_service,
)
from archub_cms.extensibility.host import get_plugin_host

collaboration_router = APIRouter(prefix="/api/platform/collaboration", tags=["collaboration"])


def _service():
    return get_archub_collaboration_service()


@collaboration_router.post("/nodes/{node_id}/comments")
def add_comment(node_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    body = str(payload.get("body") or "")
    author = str(payload.get("author") or "")
    try:
        comment = _service().add_comment(
            node_id=node_id,
            author=author,
            body=body,
            parent_comment_id=str(payload.get("parent_comment_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return comment.as_dict()


@collaboration_router.get("/nodes/{node_id}/comments")
def list_comments(node_id: str, include_resolved: bool = Query(default=True)) -> dict[str, Any]:
    return _service().thread_for_node(node_id, include_resolved=include_resolved)


@collaboration_router.post("/comments/{comment_id}/resolve")
def resolve_comment(
    comment_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    try:
        return (
            _service().resolve_comment(comment_id, actor=str(payload.get("actor") or "")).as_dict()
        )
    except CommentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="comment not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@collaboration_router.post("/comments/{comment_id}/reactions")
def react(comment_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    try:
        comment = _service().react(
            comment_id,
            user=str(payload.get("user") or ""),
            kind=str(payload.get("kind") or "like"),
        )
    except CommentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="comment not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return comment.as_dict()


@collaboration_router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str, actor: str = Query(default="")) -> dict[str, Any]:
    return {"deleted": _service().delete_comment(comment_id, actor=actor)}


@collaboration_router.get("/mentions/{username}")
def mentions_for(username: str) -> dict[str, Any]:
    return _service().mentions_for_user(username)


@collaboration_router.get("/notifications/{username}")
def notifications_for(
    username: str, limit: int = Query(default=50, ge=1, le=200)
) -> dict[str, Any]:
    plugin = get_plugin_host().plugin_instance("example.notifications")
    items = plugin.notifications_for(username, limit=limit) if plugin is not None else []
    return {"username": username, "items": items, "total": len(items)}
