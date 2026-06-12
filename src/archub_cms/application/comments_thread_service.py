"""Comments thread service: manages threaded discussions on content."""

from __future__ import annotations

__all__ = ["CommentsThreadService", "get_archub_comments_thread_service"]

from typing import Any

from archub_cms.domain.comments_thread.models import Comment, CommentThread
from archub_cms.kernel.events import EventBus


class CommentsThreadService:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def create_thread(self, node_id: str, title: str = "") -> CommentThread:
        import time

        from archub_cms.kernel.value_objects import Identity

        return CommentThread(
            thread_id=Identity.generate("thread-").value,
            node_id=node_id,
            title=title,
            created_at=time.time(),
        )

    def add_comment(self, thread_id: str, author: str, body: str, parent_id: str = "") -> Comment:
        import time

        from archub_cms.kernel.value_objects import Identity

        return Comment(
            comment_id=Identity.generate("comment-").value,
            thread_id=thread_id,
            author=author,
            body=body,
            parent_comment_id=parent_id,
            created_at=time.time(),
        )

    def resolve_comment(self, comment: Comment) -> Comment:
        comment.resolve()
        return comment

    def list_for_node(self, node_id: str) -> dict[str, Any]:
        return {"threads": [], "total": 0}


def get_archub_comments_thread_service(
    event_bus: EventBus | None = None,
) -> CommentsThreadService:
    return CommentsThreadService(event_bus=event_bus)
