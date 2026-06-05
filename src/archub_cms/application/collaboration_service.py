"""Application service for the collaboration context (comments/mentions/reactions).

Commands mutate the :class:`Comment` aggregate, persist it via the repository,
and publish domain events to the kernel event bus — so plugins (e.g. the bundled
notifications plugin) react to ``comment.created``/``mention.created`` etc. A
``mention.created`` event is emitted per newly mentioned user so a notification
fan-out is one-event-per-recipient.
"""

from __future__ import annotations

__all__ = ["CollaborationService", "get_archub_collaboration_service"]

import secrets
import time
from typing import Any

from archub_cms.domain.collaboration import events as collab_events
from archub_cms.domain.collaboration.comment import Comment, ReactionKind
from archub_cms.domain.collaboration.repository import CommentRepository
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.comment_repository import SqliteCommentRepository
from archub_cms.kernel.events import EventBus, get_event_bus


class CommentNotFoundError(LookupError):
    """Raised when a command targets a comment id that does not exist."""


class CollaborationService:
    def __init__(
        self,
        *,
        repository: CommentRepository | None = None,
        event_bus: EventBus | None = None,
        db_path: str | None = None,
    ) -> None:
        if repository is None:
            path = db_path or _default_db_path()
            repository = SqliteCommentRepository(Database(path))
        self._repo = repository
        self._bus = event_bus or get_event_bus()

    # -- commands ----------------------------------------------------------

    def add_comment(
        self,
        *,
        node_id: str,
        author: str,
        body: str,
        parent_comment_id: str = "",
    ) -> Comment:
        now = time.time()
        comment = Comment(
            comment_id=secrets.token_urlsafe(10),
            node_id=node_id,
            author=author,
            body=body,
            parent_comment_id=parent_comment_id,
            created_at=now,
            updated_at=now,
        )
        guard = comment.validate()
        if not guard.ok:
            raise ValueError(getattr(guard, "error", "invalid comment"))
        self._repo.add(comment)
        self._publish(
            collab_events.comment_created(
                comment.comment_id,
                author,
                {"node_id": node_id, "parent_comment_id": parent_comment_id, "body": body},
            )
        )
        self._emit_mentions(comment, comment.mentions, actor=author)
        return comment

    def edit_comment(self, comment_id: str, *, body: str, editor: str) -> Comment:
        comment = self._require(comment_id)
        new_mentions = comment.edit(body)
        comment.updated_at = time.time()
        self._repo.update(comment)
        self._publish(
            collab_events.comment_updated(comment_id, editor, {"node_id": comment.node_id})
        )
        self._emit_mentions(comment, new_mentions, actor=editor)
        return comment

    def resolve_comment(self, comment_id: str, *, actor: str) -> Comment:
        comment = self._require(comment_id)
        guard = comment.resolve()
        if not guard.ok:
            raise ValueError(getattr(guard, "error", "cannot resolve"))
        comment.updated_at = time.time()
        self._repo.update(comment)
        self._publish(
            collab_events.comment_resolved(comment_id, actor, {"node_id": comment.node_id})
        )
        return comment

    def delete_comment(self, comment_id: str, *, actor: str) -> bool:
        comment = self._repo.get(comment_id)
        if comment is None:
            return False
        deleted = self._repo.delete(comment_id)
        if deleted:
            self._publish(
                collab_events.comment_deleted(comment_id, actor, {"node_id": comment.node_id})
            )
        return deleted

    def react(self, comment_id: str, *, user: str, kind: ReactionKind | str) -> Comment:
        comment = self._require(comment_id)
        if comment.add_reaction(user, kind):
            comment.updated_at = time.time()
            self._repo.update(comment)
            self._publish(
                collab_events.reaction_added(
                    comment_id, user, {"node_id": comment.node_id, "kind": str(ReactionKind(kind))}
                )
            )
        return comment

    def unreact(self, comment_id: str, *, user: str, kind: ReactionKind | str) -> Comment:
        comment = self._require(comment_id)
        if comment.remove_reaction(user, kind):
            comment.updated_at = time.time()
            self._repo.update(comment)
        return comment

    # -- queries -----------------------------------------------------------

    def thread_for_node(self, node_id: str, *, include_resolved: bool = True) -> dict[str, Any]:
        comments = self._repo.list_for_node(node_id, include_resolved=include_resolved)
        roots = [c for c in comments if not c.is_reply]
        replies: dict[str, list[Comment]] = {}
        for comment in comments:
            if comment.is_reply:
                replies.setdefault(comment.parent_comment_id, []).append(comment)
        items = []
        for root in roots:
            payload = root.as_dict()
            payload["replies"] = [r.as_dict() for r in replies.get(root.comment_id, ())]
            items.append(payload)
        return {"node_id": node_id, "items": items, "total": len(comments)}

    def mentions_for_user(self, username: str) -> dict[str, Any]:
        comments = self._repo.list_mentions_for(username)
        return {
            "username": username,
            "items": [c.as_dict() for c in comments],
            "total": len(comments),
        }

    # -- internals ---------------------------------------------------------

    def _require(self, comment_id: str) -> Comment:
        comment = self._repo.get(comment_id)
        if comment is None:
            raise CommentNotFoundError(comment_id)
        return comment

    def _emit_mentions(self, comment: Comment, mentions, *, actor: str) -> None:
        for mention in mentions:
            self._publish(
                collab_events.mention_created(
                    comment.comment_id,
                    actor,
                    {"node_id": comment.node_id, "mentioned": mention.username},
                )
            )

    def _publish(self, event) -> None:
        self._bus.publish(event)


def _default_db_path() -> str:
    from archub_cms.services.cms import get_archub_cms_service

    return get_archub_cms_service().db_path


def get_archub_collaboration_service(
    *,
    repository: CommentRepository | None = None,
    event_bus: EventBus | None = None,
    db_path: str | None = None,
) -> CollaborationService:
    return CollaborationService(repository=repository, event_bus=event_bus, db_path=db_path)
