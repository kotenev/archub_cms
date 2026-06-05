"""The ``Workflow`` aggregate and its transition state machine."""

from __future__ import annotations

__all__ = [
    "WORKFLOW_TRANSITIONS",
    "Workflow",
    "WorkflowState",
    "WorkflowTransitionError",
]

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class WorkflowState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"
    TRASHED = "trashed"


# Explicit transition table — the single source of truth for legal moves.
WORKFLOW_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.DRAFT: frozenset(
        {
            WorkflowState.IN_REVIEW,
            WorkflowState.SCHEDULED,
            WorkflowState.PUBLISHED,
            WorkflowState.ARCHIVED,
            WorkflowState.TRASHED,
        }
    ),
    WorkflowState.IN_REVIEW: frozenset(
        {WorkflowState.APPROVED, WorkflowState.CHANGES_REQUESTED, WorkflowState.DRAFT}
    ),
    WorkflowState.CHANGES_REQUESTED: frozenset({WorkflowState.DRAFT, WorkflowState.IN_REVIEW}),
    WorkflowState.APPROVED: frozenset(
        {WorkflowState.SCHEDULED, WorkflowState.PUBLISHED, WorkflowState.DRAFT}
    ),
    WorkflowState.SCHEDULED: frozenset(
        {WorkflowState.PUBLISHED, WorkflowState.DRAFT, WorkflowState.UNPUBLISHED}
    ),
    WorkflowState.PUBLISHED: frozenset(
        {WorkflowState.UNPUBLISHED, WorkflowState.ARCHIVED, WorkflowState.DRAFT}
    ),
    WorkflowState.UNPUBLISHED: frozenset(
        {WorkflowState.DRAFT, WorkflowState.PUBLISHED, WorkflowState.ARCHIVED}
    ),
    WorkflowState.ARCHIVED: frozenset({WorkflowState.DRAFT, WorkflowState.TRASHED}),
    WorkflowState.TRASHED: frozenset({WorkflowState.DRAFT}),
}


class WorkflowTransitionError(ValueError):
    """Raised when a workflow transition is not permitted from the current state."""


@dataclass
class Workflow:
    """Aggregate tracking a node's review/publish lifecycle state."""

    node_id: str
    state: WorkflowState = WorkflowState.DRAFT
    assigned_to: str = ""
    scheduled_publish_at: float | None = None
    scheduled_unpublish_at: float | None = None
    note: str = ""

    def allowed_transitions(self) -> tuple[WorkflowState, ...]:
        return tuple(sorted(WORKFLOW_TRANSITIONS.get(self.state, frozenset())))

    def can_transition(self, to: WorkflowState) -> bool:
        return to in WORKFLOW_TRANSITIONS.get(self.state, frozenset())

    def transition(
        self, to: WorkflowState, *, note: str = "", assigned_to: str | None = None
    ) -> None:
        if not self.can_transition(to):
            allowed = ", ".join(self.allowed_transitions()) or "(none)"
            raise WorkflowTransitionError(
                f"cannot move from {self.state} to {to}; allowed: {allowed}"
            )
        self.state = to
        if note:
            self.note = note
        if assigned_to is not None:
            self.assigned_to = assigned_to

    @property
    def is_terminal(self) -> bool:
        return not WORKFLOW_TRANSITIONS.get(self.state, frozenset())

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "assigned_to": self.assigned_to,
            "scheduled_publish_at": self.scheduled_publish_at,
            "scheduled_unpublish_at": self.scheduled_unpublish_at,
            "note": self.note,
            "allowed_transitions": [s.value for s in self.allowed_transitions()],
            "is_terminal": self.is_terminal,
        }
