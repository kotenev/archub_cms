"""The :class:`ServiceDesk` application facade binding workflows to tickets.

It owns the registry of customizable :class:`WorkflowScheme` objects and an
in-process ticket store (plugins run sandboxed with no database handle, so the
Service Desk keeps its own state), and applies a transition's post-functions to a
ticket when it is moved. Three default schemes ship for a cloud provider:
incident management, service requests and change management.
"""

from __future__ import annotations

__all__ = ["ServiceDesk", "build_default_schemes"]

import itertools
from collections.abc import Callable, Mapping
from time import time
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.tickets import (
    CloudResource,
    Priority,
    SlaPolicy,
    Ticket,
    TicketEvent,
    TicketType,
)
from archub_cms.extensibility.example_plugins.itsm.workflow import (
    StatusCategory,
    WorkflowError,
    WorkflowScheme,
)

# Maps each ticket type to the workflow scheme that governs it by default.
_TYPE_SCHEME = {
    TicketType.INCIDENT: "incident",
    TicketType.SERVICE_REQUEST: "service_request",
    TicketType.PROBLEM: "incident",
    TicketType.CHANGE: "change",
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
    """Owns workflow schemes + an in-process ticket store for one plugin instance."""

    def __init__(
        self,
        *,
        project_prefix: str = "SD",
        provider: str = "archub-cloud",
        sla: SlaPolicy | None = None,
        clock: Callable[[], float] = time,
        schemes: dict[str, WorkflowScheme] | None = None,
    ) -> None:
        self.project_prefix = project_prefix
        self.provider = provider
        self.sla = sla or SlaPolicy()
        self._clock = clock
        self.schemes: dict[str, WorkflowScheme] = schemes or build_default_schemes()
        self._tickets: dict[str, Ticket] = {}
        self._counter = itertools.count(1)

    # -- scheme management -------------------------------------------------

    def register_scheme(self, scheme: WorkflowScheme) -> list[str]:
        """Add or replace a (customized) scheme; returns validation problems."""

        problems = scheme.validate()
        self.schemes[scheme.key] = scheme
        return problems

    def scheme_for(self, ticket_type: TicketType) -> WorkflowScheme:
        key = _TYPE_SCHEME.get(ticket_type, "incident")
        scheme = self.schemes.get(key)
        if scheme is None:
            raise WorkflowError(f"no workflow scheme {key!r} for ticket type {ticket_type.value!r}")
        return scheme

    # -- ticket lifecycle --------------------------------------------------

    def create_ticket(
        self,
        *,
        type: TicketType,
        summary: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        reporter: str = "",
        cloud: CloudResource | None = None,
        scheme_key: str = "",
    ) -> Ticket:
        scheme = self.schemes[scheme_key] if scheme_key else self.scheme_for(type)
        now = self._clock()
        key = f"{self.project_prefix}-{next(self._counter)}"
        resource = cloud or CloudResource(provider=self.provider)
        ticket = Ticket(
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
        ticket.record(TicketEvent(at=now, actor=reporter or "system", kind="created", detail=key))
        self._tickets[key] = ticket
        return ticket

    def assign(self, key: str, assignee: str, *, actor: str = "") -> Ticket:
        """Field edit: (re)assign a ticket outside of a transition, Jira-style."""

        ticket = self.get(key)
        ticket.assignee = assignee
        ticket.record(
            TicketEvent(
                at=self._clock(),
                actor=actor or assignee or "system",
                kind="assigned",
                detail=assignee,
            )
        )
        return ticket

    def available_transitions(
        self, key: str, *, actor_role: str = ""
    ) -> tuple[dict[str, Any], ...]:
        ticket = self.get(key)
        scheme = self.schemes[ticket.scheme_key]
        context = self._context(ticket, actor_role=actor_role)
        return tuple(
            transition.as_dict()
            for transition in scheme.available_transitions(ticket.status_id, context=context)
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
    ) -> Ticket:
        ticket = self.get(key)
        scheme = self.schemes[ticket.scheme_key]
        if resolution:
            ticket.resolution = resolution
        context = self._context(ticket, actor=actor, actor_role=actor_role, approved=approved)
        outcome = scheme.apply(ticket.status_id, transition_id, context=context)
        from_status = ticket.status_id
        ticket.status_id = outcome.to_status
        now = self._clock()
        self._apply_post_functions(ticket, outcome.post_functions, actor=actor, now=now)
        ticket.record(
            TicketEvent(
                at=now,
                actor=actor or "system",
                kind="transition",
                detail=f"{from_status} -> {outcome.to_status} ({outcome.transition.name})",
            )
        )
        return ticket

    def _apply_post_functions(
        self, ticket: Ticket, post_functions: tuple[str, ...], *, actor: str, now: float
    ) -> None:
        for name in post_functions:
            if name == "assign_to_actor" and actor:
                ticket.assignee = actor
            elif name == "clear_assignee":
                ticket.assignee = ""
            elif name == "stamp_resolved_at":
                ticket.resolved_at = now
            elif name == "set_resolution" and not ticket.resolution:
                ticket.resolution = "Done"

    def _context(
        self,
        ticket: Ticket,
        *,
        actor: str = "",
        actor_role: str = "",
        approved: bool = False,
    ) -> dict[str, Any]:
        return {
            "assignee": ticket.assignee,
            "resolution": ticket.resolution,
            "actor": actor,
            "actor_role": actor_role,
            "approved": approved,
            "priority": ticket.priority.value,
        }

    # -- queries -----------------------------------------------------------

    def get(self, key: str) -> Ticket:
        try:
            return self._tickets[key]
        except KeyError as exc:
            raise WorkflowError(f"unknown ticket {key!r}") from exc

    def list_tickets(
        self,
        *,
        type: TicketType | None = None,
        status_id: str = "",
        assignee: str | None = None,
    ) -> list[Ticket]:
        items = list(self._tickets.values())
        if type is not None:
            items = [t for t in items if t.type is type]
        if status_id:
            items = [t for t in items if t.status_id == status_id]
        if assignee is not None:
            items = [t for t in items if t.assignee == assignee]
        return sorted(items, key=lambda t: t.created_at)

    def queue_summary(self, mapping: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Counts by status category + SLA breaches, for a dashboard widget."""

        now = self._clock()
        by_category = {category.value: 0 for category in StatusCategory}
        by_priority: dict[str, int] = {}
        response_breaches = 0
        resolution_breaches = 0
        open_total = 0
        for ticket in self._tickets.values():
            scheme = self.schemes.get(ticket.scheme_key)
            category = (
                scheme.status(ticket.status_id).category.value
                if scheme and ticket.status_id in scheme.statuses
                else StatusCategory.TODO.value
            )
            by_category[category] = by_category.get(category, 0) + 1
            by_priority[ticket.priority.value] = by_priority.get(ticket.priority.value, 0) + 1
            if category != StatusCategory.DONE.value:
                open_total += 1
            if ticket.response_breached(now):
                response_breaches += 1
            if ticket.resolution_breached(now):
                resolution_breaches += 1
        return {
            "total": len(self._tickets),
            "open": open_total,
            "by_category": by_category,
            "by_priority": by_priority,
            "sla_response_breaches": response_breaches,
            "sla_resolution_breaches": resolution_breaches,
        }
