"""Workflow repository adapter mapping legacy workflow reads to the aggregate."""

from __future__ import annotations

__all__ = ["CmsWorkflowRepository"]

from typing import Any

from archub_cms.domain.workflow.workflow import Workflow, WorkflowState
from archub_cms.services.cms import ArcHubCMSService, ContentWorkflow, get_archub_cms_service


def _state(value: str) -> WorkflowState:
    try:
        return WorkflowState(value)
    except ValueError:
        return WorkflowState.DRAFT


def _workflow(workflow: ContentWorkflow) -> Workflow:
    return Workflow(
        node_id=workflow.node_id,
        state=_state(workflow.state),
        assigned_to=workflow.assigned_to,
        scheduled_publish_at=workflow.scheduled_publish_at,
        scheduled_unpublish_at=workflow.scheduled_unpublish_at,
        note=workflow.note,
    )


class CmsWorkflowRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def get(self, node_id: str) -> Workflow:
        return _workflow(self._cms.get_workflow(node_id))

    def report(self, *, limit: int = 200) -> dict[str, Any]:
        return self._cms.workflow_report(limit=limit)
