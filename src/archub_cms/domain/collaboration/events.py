"""Domain event factories for the collaboration context."""

from __future__ import annotations

__all__ = [
    "COMMENT_CREATED",
    "COMMENT_DELETED",
    "COMMENT_RESOLVED",
    "COMMENT_UPDATED",
    "MENTION_CREATED",
    "REACTION_ADDED",
    "comment_created",
    "comment_deleted",
    "comment_resolved",
    "comment_updated",
    "mention_created",
    "reaction_added",
]

from typing import Any

from archub_cms.kernel.events import ArcHubDomainEvent

COMMENT_CREATED = "comment.created"
COMMENT_UPDATED = "comment.updated"
COMMENT_DELETED = "comment.deleted"
COMMENT_RESOLVED = "comment.resolved"
MENTION_CREATED = "mention.created"
REACTION_ADDED = "reaction.added"


def _event(
    event_type: str, comment_id: str, actor: str, metadata: dict[str, Any]
) -> ArcHubDomainEvent:
    return ArcHubDomainEvent(
        event_type=event_type, aggregate_id=comment_id, actor=actor, metadata=metadata
    )


def comment_created(comment_id: str, actor: str, metadata: dict[str, Any]) -> ArcHubDomainEvent:
    return _event(COMMENT_CREATED, comment_id, actor, metadata)


def comment_updated(comment_id: str, actor: str, metadata: dict[str, Any]) -> ArcHubDomainEvent:
    return _event(COMMENT_UPDATED, comment_id, actor, metadata)


def comment_deleted(comment_id: str, actor: str, metadata: dict[str, Any]) -> ArcHubDomainEvent:
    return _event(COMMENT_DELETED, comment_id, actor, metadata)


def comment_resolved(comment_id: str, actor: str, metadata: dict[str, Any]) -> ArcHubDomainEvent:
    return _event(COMMENT_RESOLVED, comment_id, actor, metadata)


def mention_created(comment_id: str, actor: str, metadata: dict[str, Any]) -> ArcHubDomainEvent:
    return _event(MENTION_CREATED, comment_id, actor, metadata)


def reaction_added(comment_id: str, actor: str, metadata: dict[str, Any]) -> ArcHubDomainEvent:
    return _event(REACTION_ADDED, comment_id, actor, metadata)
