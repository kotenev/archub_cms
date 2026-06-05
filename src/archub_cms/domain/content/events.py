"""Domain event factories for the content context.

Event types use the same dotted names the legacy activity log already emits
(``content.created``/``content.published``/...), so plugins and webhooks share
one vocabulary regardless of which entry point triggered the change.
"""

from __future__ import annotations

__all__ = [
    "CONTENT_CREATED",
    "CONTENT_DELETED",
    "CONTENT_PUBLISHED",
    "CONTENT_UNPUBLISHED",
    "CONTENT_UPDATED",
    "node_created",
    "node_deleted",
    "node_published",
    "node_unpublished",
    "node_updated",
]

from typing import Any

from archub_cms.kernel.events import ArcHubDomainEvent

CONTENT_CREATED = "content.created"
CONTENT_UPDATED = "content.updated"
CONTENT_PUBLISHED = "content.published"
CONTENT_UNPUBLISHED = "content.unpublished"
CONTENT_DELETED = "content.deleted"


def _event(
    event_type: str, node_id: str, actor: str, metadata: dict[str, Any] | None
) -> ArcHubDomainEvent:
    return ArcHubDomainEvent(
        event_type=event_type,
        aggregate_id=node_id,
        actor=actor,
        metadata=metadata or {},
    )


def node_created(
    node_id: str, actor: str, metadata: dict[str, Any] | None = None
) -> ArcHubDomainEvent:
    return _event(CONTENT_CREATED, node_id, actor, metadata)


def node_updated(
    node_id: str, actor: str, metadata: dict[str, Any] | None = None
) -> ArcHubDomainEvent:
    return _event(CONTENT_UPDATED, node_id, actor, metadata)


def node_published(
    node_id: str, actor: str, metadata: dict[str, Any] | None = None
) -> ArcHubDomainEvent:
    return _event(CONTENT_PUBLISHED, node_id, actor, metadata)


def node_unpublished(
    node_id: str, actor: str, metadata: dict[str, Any] | None = None
) -> ArcHubDomainEvent:
    return _event(CONTENT_UNPUBLISHED, node_id, actor, metadata)


def node_deleted(
    node_id: str, actor: str, metadata: dict[str, Any] | None = None
) -> ArcHubDomainEvent:
    return _event(CONTENT_DELETED, node_id, actor, metadata)
