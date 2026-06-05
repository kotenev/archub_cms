"""The ``Comment`` aggregate root."""

from __future__ import annotations

__all__ = ["Comment", "ReactionKind"]

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from archub_cms.domain.collaboration.value_objects import Mention, extract_mentions
from archub_cms.kernel.result import Err, Ok, Result


class ReactionKind(StrEnum):
    LIKE = "like"
    CELEBRATE = "celebrate"
    INSIGHTFUL = "insightful"
    CURIOUS = "curious"
    THANKS = "thanks"


@dataclass
class Comment:
    """A threaded comment on a content node, with mentions and reactions."""

    comment_id: str
    node_id: str
    author: str
    body: str
    parent_comment_id: str = ""
    mentions: tuple[Mention, ...] = ()
    reactions: dict[str, set[str]] = field(default_factory=dict)
    resolved: bool = False
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.mentions:
            self.mentions = extract_mentions(self.body)

    @property
    def is_reply(self) -> bool:
        return bool(self.parent_comment_id)

    def validate(self) -> Result[bool, str]:
        if not self.author.strip():
            return Err("comment author is required")
        if not self.body.strip():
            return Err("comment body cannot be empty")
        return Ok(True)

    def edit(self, body: str) -> tuple[Mention, ...]:
        """Update the body; return mentions that are newly added by this edit."""
        before = set(self.mentions)
        self.body = body
        self.mentions = extract_mentions(body)
        return tuple(m for m in self.mentions if m not in before)

    def resolve(self) -> Result[bool, str]:
        if self.resolved:
            return Err("comment already resolved")
        self.resolved = True
        return Ok(True)

    def reopen(self) -> None:
        self.resolved = False

    def add_reaction(self, user: str, kind: ReactionKind | str) -> bool:
        """Add a reaction; return True if it was newly added."""
        key = str(ReactionKind(kind))
        users = self.reactions.setdefault(key, set())
        clean = user.strip().casefold()
        if clean in users:
            return False
        users.add(clean)
        return True

    def remove_reaction(self, user: str, kind: ReactionKind | str) -> bool:
        key = str(ReactionKind(kind))
        users = self.reactions.get(key)
        clean = user.strip().casefold()
        if not users or clean not in users:
            return False
        users.discard(clean)
        if not users:
            self.reactions.pop(key, None)
        return True

    def reaction_counts(self) -> dict[str, int]:
        return {kind: len(users) for kind, users in self.reactions.items() if users}

    def as_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "node_id": self.node_id,
            "author": self.author,
            "body": self.body,
            "parent_comment_id": self.parent_comment_id,
            "is_reply": self.is_reply,
            "mentions": [m.username for m in self.mentions],
            "reactions": self.reaction_counts(),
            "resolved": self.resolved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
