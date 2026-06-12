"""Repository port for the workflow context."""

from __future__ import annotations

__all__ = ["WorkflowRepository"]

from typing import Any, Protocol, runtime_checkable

from archub_cms.domain.workflow.workflow import Workflow


@runtime_checkable
class WorkflowRepository(Protocol):
    def get(self, node_id: str) -> Workflow: ...

    def report(self, *, limit: int = 200) -> dict[str, Any]: ...
