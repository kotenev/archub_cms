"""Repository port for the collaboration context."""

from __future__ import annotations

__all__ = ["CommentRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.collaboration.comment import Comment


@runtime_checkable
class CommentRepository(Protocol):
    def add(self, comment: Comment) -> None: ...

    def get(self, comment_id: str) -> Comment | None: ...

    def update(self, comment: Comment) -> None: ...

    def delete(self, comment_id: str) -> bool: ...

    def list_for_node(self, node_id: str, *, include_resolved: bool = True) -> list[Comment]: ...

    def list_mentions_for(self, username: str) -> list[Comment]: ...
