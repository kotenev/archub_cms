"""Application service for the workflow context (review/approval state machine).

``WorkflowQueryService`` reads the current state and allowed transitions.
``WorkflowCommandService.transition`` loads the :class:`Workflow` aggregate,
asks it to transition (the aggregate enforces the state machine), persists via
the legacy service, and publishes ``workflow.transitioned`` to the kernel bus.
"""

from __future__ import annotations

__all__ = [
    "WorkflowCommandService",
    "WorkflowQueryService",
    "get_archub_workflow_query_service",
]

from typing import Any

from archub_cms.domain.workflow.repository import WorkflowRepository
from archub_cms.domain.workflow.workflow import Workflow, WorkflowState, WorkflowTransitionError
from archub_cms.infrastructure.sqlite.workflow_repository import CmsWorkflowRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class WorkflowQueryService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repo = repository

    def get(self, node_id: str) -> dict[str, Any]:
        return self._repo.get(node_id).as_dict()

    def allowed_transitions(self, node_id: str) -> dict[str, Any]:
        workflow = self._repo.get(node_id)
        return {
            "node_id": node_id,
            "state": workflow.state.value,
            "allowed_transitions": [s.value for s in workflow.allowed_transitions()],
        }

    def report(self, *, limit: int = 200) -> dict[str, Any]:
        return self._repo.report(limit=limit)


class WorkflowCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: WorkflowRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsWorkflowRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def transition(
        self,
        node_id: str,
        to: str,
        *,
        actor: str,
        note: str = "",
        assigned_to: str | None = None,
        scheduled_publish_at: float | None = None,
        scheduled_unpublish_at: float | None = None,
    ) -> Workflow:
        try:
            target = WorkflowState(to)
        except ValueError as exc:
            raise WorkflowTransitionError(f"unknown workflow state: {to}") from exc

        workflow = self._repo.get(node_id)
        from_state = workflow.state
        workflow.transition(target, note=note, assigned_to=assigned_to)  # may raise
        if scheduled_publish_at is not None:
            workflow.scheduled_publish_at = scheduled_publish_at
        if scheduled_unpublish_at is not None:
            workflow.scheduled_unpublish_at = scheduled_unpublish_at

        self._cms.upsert_workflow(
            node_id=node_id,
            state=workflow.state.value,
            assigned_to=workflow.assigned_to,
            scheduled_publish_at=workflow.scheduled_publish_at,
            scheduled_unpublish_at=workflow.scheduled_unpublish_at,
            note=workflow.note,
            updated_by=actor,
        )
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="workflow.transitioned",
                aggregate_id=node_id,
                actor=actor,
                metadata={"from": from_state.value, "to": workflow.state.value},
            )
        )
        return workflow


def get_archub_workflow_query_service(
    *, cms: ArcHubCMSService | None = None, repository: WorkflowRepository | None = None
) -> WorkflowQueryService:
    return WorkflowQueryService(repository or CmsWorkflowRepository(cms))
