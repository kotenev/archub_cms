"""Collaboration bounded context: Confluence-style comments, @mentions, reactions.

A :class:`Comment` is the aggregate root; it is attached to a content node, can
be threaded (a reply points at a parent comment), carries extracted ``@mentions``
and emoji ``reactions``, and can be resolved. State changes produce domain events
(``comment.created``, ``mention.created``, ``reaction.added`` …) that flow over
the kernel event bus to plugins (e.g. notifications).
"""

from __future__ import annotations

from archub_cms.domain.collaboration.comment import Comment, ReactionKind
from archub_cms.domain.collaboration.events import (
    COMMENT_CREATED,
    COMMENT_DELETED,
    COMMENT_RESOLVED,
    COMMENT_UPDATED,
    MENTION_CREATED,
    REACTION_ADDED,
)
from archub_cms.domain.collaboration.repository import CommentRepository
from archub_cms.domain.collaboration.value_objects import Mention, extract_mentions

__all__ = [
    "COMMENT_CREATED",
    "COMMENT_DELETED",
    "COMMENT_RESOLVED",
    "COMMENT_UPDATED",
    "MENTION_CREATED",
    "REACTION_ADDED",
    "Comment",
    "CommentRepository",
    "Mention",
    "ReactionKind",
    "extract_mentions",
]
