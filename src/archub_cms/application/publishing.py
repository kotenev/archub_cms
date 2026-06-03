"""Publishing and lifecycle application service."""

from __future__ import annotations

__all__ = [
    "PublishingCommandResult",
    "ArcHubPublishingService",
    "get_archub_publishing_service",
]

import logging
from dataclasses import dataclass, field
from typing import Any

from archub_cms.domain.events import ArcHubDomainEvent, content_event
from archub_cms.services.cms import (
    ArcHubCMSService,
    ContentNode,
    ContentWorkflow,
    get_archub_cms_service,
)

logger = logging.getLogger("archub_cms")


@dataclass(frozen=True)
class PublishingCommandResult:
    """Result returned by lifecycle commands.

    `events` are intentionally explicit so future adapters can persist, publish,
    or inspect them without route handlers knowing storage details.
    """

    action: str
    node_id: str = ""
    node: ContentNode | None = None
    workflow: ContentWorkflow | None = None
    report: dict[str, Any] = field(default_factory=dict)
    events: tuple[ArcHubDomainEvent, ...] = ()
    runtime_export: dict[str, Any] | None = None
    runtime_export_error: str = ""

    @property
    def runtime_exported(self) -> bool:
        return self.runtime_export is not None and not self.runtime_export_error

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "node_id": self.node_id,
            "node": self.node.__dict__ if self.node is not None else None,
            "workflow": self.workflow.__dict__ if self.workflow is not None else None,
            "report": self.report,
            "events": [event.as_dict() for event in self.events],
            "runtime_export": self.runtime_export,
            "runtime_export_error": self.runtime_export_error,
        }


class ArcHubPublishingService:
    """Application boundary for content lifecycle commands."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def publish(self, node_id: str, *, actor: str) -> PublishingCommandResult:
        node = self._cms.publish_node(node_id, published_by=actor)
        events = (
            content_event(
                "content.published",
                node_id=node.node_id,
                actor=actor,
                metadata=_node_metadata(node),
            ),
        )
        runtime_export, runtime_error = self._refresh_runtime_export()
        return PublishingCommandResult(
            action="publish",
            node_id=node.node_id,
            node=node,
            events=events,
            runtime_export=runtime_export,
            runtime_export_error=runtime_error,
        )

    def unpublish(self, node_id: str, *, actor: str) -> PublishingCommandResult:
        node = self._cms.unpublish_node(node_id, updated_by=actor)
        events = (
            content_event(
                "content.unpublished",
                node_id=node.node_id,
                actor=actor,
                metadata=_node_metadata(node),
            ),
        )
        runtime_export, runtime_error = self._refresh_runtime_export()
        return PublishingCommandResult(
            action="unpublish",
            node_id=node.node_id,
            node=node,
            events=events,
            runtime_export=runtime_export,
            runtime_export_error=runtime_error,
        )

    def update_workflow(
        self,
        *,
        node_id: str,
        state: str,
        assigned_to: str = "",
        scheduled_publish_at: float | None = None,
        scheduled_unpublish_at: float | None = None,
        note: str = "",
        actor: str,
    ) -> PublishingCommandResult:
        workflow = self._cms.upsert_workflow(
            node_id=node_id,
            state=state,
            assigned_to=assigned_to,
            scheduled_publish_at=scheduled_publish_at,
            scheduled_unpublish_at=scheduled_unpublish_at,
            note=note,
            updated_by=actor,
        )
        return PublishingCommandResult(
            action="workflow.update",
            node_id=node_id,
            workflow=workflow,
            events=(
                content_event(
                    "content.workflow.updated",
                    node_id=node_id,
                    actor=actor,
                    metadata={
                        "state": workflow.state,
                        "assigned_to": workflow.assigned_to,
                        "scheduled_publish_at": workflow.scheduled_publish_at,
                        "scheduled_unpublish_at": workflow.scheduled_unpublish_at,
                    },
                ),
            ),
        )

    def apply_due_workflows(self, *, actor: str) -> PublishingCommandResult:
        report = self._cms.apply_due_workflows(updated_by=actor)
        events = tuple(
            content_event(
                f"content.{item.get('action', 'workflow')!s}ed",
                node_id=str(item.get("node_id", "")),
                actor=actor,
                metadata={"source": "workflow.apply_due"},
            )
            for item in report.get("applied", [])
            if str(item.get("node_id", "")).strip()
        )
        runtime_export = None
        runtime_error = ""
        if int(report.get("applied_count") or 0):
            runtime_export, runtime_error = self._refresh_runtime_export()
        return PublishingCommandResult(
            action="workflow.apply_due",
            report=report,
            events=events,
            runtime_export=runtime_export,
            runtime_export_error=runtime_error,
        )

    def delete(self, node_id: str, *, actor: str) -> PublishingCommandResult:
        self._cms.delete_node(node_id, deleted_by=actor)
        runtime_export, runtime_error = self._refresh_runtime_export()
        return PublishingCommandResult(
            action="delete",
            node_id=node_id,
            events=(content_event("content.deleted", node_id=node_id, actor=actor),),
            runtime_export=runtime_export,
            runtime_export_error=runtime_error,
        )

    def restore_from_trash(self, node_id: str, *, actor: str) -> PublishingCommandResult:
        node = self._cms.restore_trashed_node(node_id, restored_by=actor)
        runtime_export, runtime_error = self._refresh_runtime_export()
        return PublishingCommandResult(
            action="restore_from_trash",
            node_id=node.node_id,
            node=node,
            events=(
                content_event(
                    "content.restored",
                    node_id=node.node_id,
                    actor=actor,
                    metadata=_node_metadata(node),
                ),
            ),
            runtime_export=runtime_export,
            runtime_export_error=runtime_error,
        )

    def purge(self, node_id: str, *, actor: str) -> PublishingCommandResult:
        self._cms.purge_trashed_node(node_id, purged_by=actor)
        runtime_export, runtime_error = self._refresh_runtime_export()
        return PublishingCommandResult(
            action="purge",
            node_id=node_id,
            events=(content_event("content.purged", node_id=node_id, actor=actor),),
            runtime_export=runtime_export,
            runtime_export_error=runtime_error,
        )

    def _refresh_runtime_export(self) -> tuple[dict[str, Any] | None, str]:
        try:
            return self._cms.export_runtime_content(), ""
        except Exception as exc:
            logger.warning("ArcHub runtime export refresh failed", exc_info=True)
            return None, str(exc)


def get_archub_publishing_service(cms: ArcHubCMSService | None = None) -> ArcHubPublishingService:
    return ArcHubPublishingService(cms=cms)


def _node_metadata(node: ContentNode) -> dict[str, Any]:
    return {
        "route_path": node.route_path,
        "content_type_alias": node.content_type_alias,
        "status": node.status,
    }
