"""Comment thread domain models."""

from __future__ import annotations

__all__ = ["Comment", "CommentThread", "CommentStatus"]

from dataclasses import dataclass, field
from typing import Any


class CommentStatus:
    ACTIVE = "active"
    RESOLVED = "resolved"
    HIDDEN = "hidden"


@dataclass
class Comment:
    comment_id: str
    thread_id: str
    author: str
    body: str
    parent_comment_id: str = ""
    status: str = CommentStatus.ACTIVE
    created_at: float = 0.0
    updated_at: float = 0.0
    reactions: dict[str, list[str]] = field(default_factory=dict)

    def resolve(self) -> None:
        self.status = CommentStatus.RESOLVED

    def hide(self) -> None:
        self.status = CommentStatus.HIDDEN

    def add_reaction(self, emoji: str, username: str) -> None:
        self.reactions.setdefault(emoji, [])
        if username not in self.reactions[emoji]:
            self.reactions[emoji].append(username)

    def remove_reaction(self, emoji: str, username: str) -> None:
        if emoji in self.reactions:
            self.reactions[emoji] = [u for u in self.reactions[emoji] if u != username]

    def as_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "thread_id": self.thread_id,
            "author": self.author,
            "body": self.body,
            "parent_comment_id": self.parent_comment_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reactions": self.reactions,
        }


@dataclass
class CommentThread:
    thread_id: str
    node_id: str
    title: str = ""
    resolved: bool = False
    created_at: float = 0.0
    comment_count: int = 0

    def mark_resolved(self) -> None:
        self.resolved = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "node_id": self.node_id,
            "title": self.title,
            "resolved": self.resolved,
            "created_at": self.created_at,
            "comment_count": self.comment_count,
        }
