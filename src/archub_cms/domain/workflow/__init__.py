"""Workflow bounded context: Confluence-style review/approval state machine.

Content moves through an explicit, guarded state machine
(draft → in_review → approved/changes_requested → scheduled/published → …). The
allowed transitions live in :data:`WORKFLOW_TRANSITIONS`; the :class:`Workflow`
aggregate enforces them, so illegal jumps are rejected in the domain.
"""

from __future__ import annotations

from archub_cms.domain.workflow.repository import WorkflowRepository
from archub_cms.domain.workflow.workflow import (
    WORKFLOW_TRANSITIONS,
    Workflow,
    WorkflowState,
    WorkflowTransitionError,
)

__all__ = [
    "WORKFLOW_TRANSITIONS",
    "Workflow",
    "WorkflowRepository",
    "WorkflowState",
    "WorkflowTransitionError",
]
