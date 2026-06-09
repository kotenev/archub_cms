"""The :class:`ServiceDesk` application facade binding workflows to requests.

It owns the registry of customizable :class:`WorkflowScheme` objects and a
:class:`RequestRepository` (SQLite-backed by default; in-memory for tests), and
applies a transition's post-functions to a request when it is moved. Three default
schemes ship for a cloud provider: incident management, service-request fulfilment
and change management.
"""

from __future__ import annotations

__all__ = ["RequestNotFoundError", "ServiceDesk", "build_default_schemes"]

from collections.abc import Callable
from time import time
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.repository import (
    InMemoryRequestRepository,
    RequestRepository,
    SqliteRequestRepository,
)
from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    Request,
    RequestEvent,
    RequestType,
    SlaPolicy,
)
from archub_cms.extensibility.example_plugins.itsm.workflow import (
    StatusCategory,
    WorkflowError,
    WorkflowScheme,
)
from archub_cms.infrastructure.db.database import Database


class RequestNotFoundError(WorkflowError):
    """Raised when a request key does not exist (mapped to HTTP 404 by the API)."""


# Maps each request type to the workflow scheme that governs it by default.
_TYPE_SCHEME = {
    RequestType.INCIDENT: "incident",
    RequestType.SERVICE_REQUEST: "service_request",
    RequestType.PROBLEM: "incident",
    RequestType.CHANGE: "change",
}


def build_default_schemes() -> dict[str, WorkflowScheme]:
    """Three production-shaped schemes a cloud Service Desk starts with."""

    incident = (
        WorkflowScheme("incident", "Incident Management", "Cloud incident lifecycle")
        .add_status("open", "Open", StatusCategory.TODO, initial=True)
        .add_status("triaged", "Triaged", StatusCategory.TODO)
        .add_status("in_progress", "In Progress", StatusCategory.IN_PROGRESS)
        .add_status("pending", "Pending Customer", StatusCategory.IN_PROGRESS)
        .add_status("resolved", "Resolved", StatusCategory.DONE)
        .add_status("closed", "Closed", StatusCategory.DONE)
        .add_status("cancelled", "Cancelled", StatusCategory.DONE)
        .add_transition("triage", "Triage", "triaged", ["open"])
        .add_transition(
            "start",
            "Start Progress",
            "in_progress",
            ["triaged", "pending"],
            conditions=["is_agent"],
            post_functions=["assign_to_actor"],
        )
        .add_transition("wait", "Wait for Customer", "pending", ["in_progress"])
        .add_transition(
            "resolve",
            "Resolve",
            "resolved",
            ["in_progress"],
            conditions=["resolution_set"],
            post_functions=["stamp_resolved_at"],
        )
        .add_transition("close", "Close", "closed", ["resolved"])
        .add_transition("reopen", "Reopen", "open", ["resolved", "closed"])
        # Global "Cancel": fireable from any non-terminal status, like Jira "All".
        .add_transition("cancel", "Cancel", "cancelled", post_functions=["stamp_resolved_at"])
    )

    service_request = (
        WorkflowScheme("service_request", "Service Request", "Cloud service request fulfilment")
        .add_status("submitted", "Submitted", StatusCategory.TODO, initial=True)
        .add_status("approval", "Awaiting Approval", StatusCategory.TODO)
        .add_status("fulfilment", "In Fulfilment", StatusCategory.IN_PROGRESS)
        .add_status("delivered", "Delivered", StatusCategory.DONE)
        .add_status("rejected", "Rejected", StatusCategory.DONE)
        .add_transition("request_approval", "Request Approval", "approval", ["submitted"])
        .add_transition(
            "approve",
            "Approve",
            "fulfilment",
            ["approval"],
            conditions=["is_manager"],
            post_functions=["assign_to_actor"],
        )
        .add_transition("reject", "Reject", "rejected", ["approval"], conditions=["is_manager"])
        .add_transition(
            "deliver",
            "Deliver",
            "delivered",
            ["fulfilment"],
            post_functions=["stamp_resolved_at"],
        )
    )

    change = (
        WorkflowScheme("change", "Change Management", "Cloud change advisory workflow")
        .add_status("draft", "Draft", StatusCategory.TODO, initial=True)
        .add_status("review", "In Review", StatusCategory.TODO)
        .add_status("approved", "Approved", StatusCategory.IN_PROGRESS)
        .add_status("implementing", "Implementing", StatusCategory.IN_PROGRESS)
        .add_status("done", "Implemented", StatusCategory.DONE)
        .add_status("rolled_back", "Rolled Back", StatusCategory.DONE)
        .add_transition("submit", "Submit for Review", "review", ["draft"])
        .add_transition(
            "approve",
            "Approve (CAB)",
            "approved",
            ["review"],
            conditions=["change_approved", "is_manager"],
        )
        .add_transition("reject", "Send Back", "draft", ["review"])
        .add_transition("implement", "Start Implementation", "implementing", ["approved"])
        .add_transition(
            "complete",
            "Complete",
            "done",
            ["implementing"],
            post_functions=["stamp_resolved_at"],
        )
        .add_transition(
            "rollback",
            "Roll Back",
            "rolled_back",
            ["implementing"],
            post_functions=["stamp_resolved_at"],
        )
    )

    return {scheme.key: scheme for scheme in (incident, service_request, change)}


class ServiceDesk:
    """Owns workflow schemes + a persistent request store for one plugin instance."""

    def __init__(
        self,
        *,
        project_prefix: str = "REQ",
        provider: str = "archub-cloud",
        sla: SlaPolicy | None = None,
        clock: Callable[[], float] = time,
        schemes: dict[str, WorkflowScheme] | None = None,
        repository: RequestRepository | None = None,
        database: Database | None = None,
    ) -> None:
        self.project_prefix = project_prefix
        self.provider = provider
        self.sla = sla or SlaPolicy()
        self._clock = clock
        self.schemes: dict[str, WorkflowScheme] = schemes or build_default_schemes()
        if repository is not None:
            self._repo: RequestRepository = repository
        elif database is not None:
            self._repo = SqliteRequestRepository(database)
        else:
            self._repo = InMemoryRequestRepository()

    @property
    def repository(self) -> RequestRepository:
        return self._repo

    # -- scheme management -------------------------------------------------

    def register_scheme(self, scheme: WorkflowScheme) -> list[str]:
        """Add or replace a (customized) scheme; returns validation problems."""

        problems = scheme.validate()
        self.schemes[scheme.key] = scheme
        return problems

    def scheme_for(self, request_type: RequestType) -> WorkflowScheme:
        key = _TYPE_SCHEME.get(request_type, "incident")
        scheme = self.schemes.get(key)
        if scheme is None:
            raise WorkflowError(
                f"no workflow scheme {key!r} for request type {request_type.value!r}"
            )
        return scheme

    # -- request lifecycle -------------------------------------------------

    def create_request(
        self,
        *,
        type: RequestType,
        summary: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        reporter: str = "",
        cloud: CloudResource | None = None,
        scheme_key: str = "",
    ) -> Request:
        scheme = self.schemes[scheme_key] if scheme_key else self.scheme_for(type)
        now = self._clock()
        key = self._repo.next_key(self.project_prefix)
        resource = cloud or CloudResource(provider=self.provider)
        request = Request(
            key=key,
            type=type,
            summary=summary,
            description=description,
            scheme_key=scheme.key,
            status_id=scheme.initial_status_id,
            priority=priority,
            reporter=reporter,
            cloud=resource,
            created_at=now,
            updated_at=now,
            sla_response_due=now + self.sla.response_minutes(priority) * 60.0,
            sla_resolution_due=now + self.sla.resolution_minutes(priority) * 60.0,
        )
        request.record(RequestEvent(at=now, actor=reporter or "system", kind="created", detail=key))
        self._repo.save(request)
        return request

    def assign(self, key: str, assignee: str, *, actor: str = "") -> Request:
        """Field edit: (re)assign a request outside of a transition, Jira-style."""

        request = self.get(key)
        request.assignee = assignee
        request.record(
            RequestEvent(
                at=self._clock(),
                actor=actor or assignee or "system",
                kind="assigned",
                detail=assignee,
            )
        )
        self._repo.save(request)
        return request

    def available_transitions(
        self, key: str, *, actor_role: str = ""
    ) -> tuple[dict[str, Any], ...]:
        request = self.get(key)
        scheme = self.schemes[request.scheme_key]
        context = self._context(request, actor_role=actor_role)
        return tuple(
            transition.as_dict()
            for transition in scheme.available_transitions(request.status_id, context=context)
        )

    def transition(
        self,
        key: str,
        transition_id: str,
        *,
        actor: str = "",
        actor_role: str = "",
        resolution: str = "",
        approved: bool = False,
    ) -> Request:
        request = self.get(key)
        scheme = self.schemes[request.scheme_key]
        if resolution:
            request.resolution = resolution
        context = self._context(request, actor=actor, actor_role=actor_role, approved=approved)
        outcome = scheme.apply(request.status_id, transition_id, context=context)
        from_status = request.status_id
        request.status_id = outcome.to_status
        now = self._clock()
        self._apply_post_functions(request, outcome.post_functions, actor=actor, now=now)
        request.record(
            RequestEvent(
                at=now,
                actor=actor or "system",
                kind="transition",
                detail=f"{from_status} -> {outcome.to_status} ({outcome.transition.name})",
            )
        )
        self._repo.save(request)
        return request

    def _apply_post_functions(
        self, request: Request, post_functions: tuple[str, ...], *, actor: str, now: float
    ) -> None:
        for name in post_functions:
            if name == "assign_to_actor" and actor:
                request.assignee = actor
            elif name == "clear_assignee":
                request.assignee = ""
            elif name == "stamp_resolved_at":
                request.resolved_at = now
            elif name == "set_resolution" and not request.resolution:
                request.resolution = "Done"

    def _context(
        self,
        request: Request,
        *,
        actor: str = "",
        actor_role: str = "",
        approved: bool = False,
    ) -> dict[str, Any]:
        return {
            "assignee": request.assignee,
            "resolution": request.resolution,
            "actor": actor,
            "actor_role": actor_role,
            "approved": approved,
            "priority": request.priority.value,
        }

    # -- queries -----------------------------------------------------------

    def get(self, key: str) -> Request:
        request = self._repo.get(key)
        if request is None:
            raise RequestNotFoundError(f"unknown request {key!r}")
        return request

    def list_requests(
        self,
        *,
        type: RequestType | None = None,
        status_id: str = "",
        assignee: str | None = None,
    ) -> list[Request]:
        items = self._repo.list_all()
        if type is not None:
            items = [r for r in items if r.type is type]
        if status_id:
            items = [r for r in items if r.status_id == status_id]
        if assignee is not None:
            items = [r for r in items if r.assignee == assignee]
        return items

    def queue_summary(self) -> dict[str, Any]:
        """Counts by status category + SLA breaches, for a dashboard widget."""

        now = self._clock()
        requests = self._repo.list_all()
        by_category = {category.value: 0 for category in StatusCategory}
        by_priority: dict[str, int] = {}
        response_breaches = 0
        resolution_breaches = 0
        open_total = 0
        for request in requests:
            scheme = self.schemes.get(request.scheme_key)
            category = (
                scheme.status(request.status_id).category.value
                if scheme and request.status_id in scheme.statuses
                else StatusCategory.TODO.value
            )
            by_category[category] = by_category.get(category, 0) + 1
            by_priority[request.priority.value] = by_priority.get(request.priority.value, 0) + 1
            if category != StatusCategory.DONE.value:
                open_total += 1
            if request.response_breached(now):
                response_breaches += 1
            if request.resolution_breached(now):
                resolution_breaches += 1
        return {
            "total": len(requests),
            "open": open_total,
            "by_category": by_category,
            "by_priority": by_priority,
            "sla_response_breaches": response_breaches,
            "sla_resolution_breaches": resolution_breaches,
        }
