"""A Jira-style customizable workflow engine.

A :class:`WorkflowScheme` is an explicit state machine an administrator builds at
runtime: named :class:`WorkflowStatus` nodes (each in a To-Do / In-Progress / Done
category) connected by guarded :class:`WorkflowTransition` edges. Transitions may
be *global* (empty ``from_statuses`` — fireable from any status, like Jira's "All"
transitions), may declare **conditions** (named predicates that must all pass) and
**post-functions** (named side-effects the application layer applies to the issue).

The engine is deliberately framework- and storage-agnostic so the same scheme can
drive a request, be validated for reachability, and be serialized to BPMN.
"""

from __future__ import annotations

__all__ = [
    "CONDITION_REGISTRY",
    "StatusCategory",
    "WorkflowError",
    "WorkflowScheme",
    "WorkflowStatus",
    "WorkflowTransition",
    "register_condition",
]

import re
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_") or "node"


class StatusCategory(StrEnum):
    """Jira-style status categories that colour a board and bound the lifecycle."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class WorkflowError(ValueError):
    """Raised when a transition is illegal or a scheme is malformed."""


# -- conditions ------------------------------------------------------------
# Conditions are named predicates evaluated against a context Mapping at the
# moment a transition is attempted. A plugin (or host) registers its own here,
# which is how the workflow stays customizable without touching engine code.

ConditionFn = Callable[[Mapping[str, Any]], bool]

CONDITION_REGISTRY: dict[str, ConditionFn] = {
    "assignee_set": lambda ctx: bool(ctx.get("assignee")),
    "resolution_set": lambda ctx: bool(ctx.get("resolution")),
    "is_agent": lambda ctx: ctx.get("actor_role") in {"agent", "manager", "admin"},
    "is_manager": lambda ctx: ctx.get("actor_role") in {"manager", "admin"},
    "change_approved": lambda ctx: bool(ctx.get("approved")),
}


def register_condition(name: str, predicate: ConditionFn) -> None:
    """Register a named transition condition usable by any workflow scheme."""

    CONDITION_REGISTRY[name] = predicate


@dataclass(frozen=True)
class WorkflowStatus:
    """A single state in a workflow (e.g. ``Open``, ``In Progress``, ``Resolved``)."""

    id: str
    name: str
    category: StatusCategory = StatusCategory.TODO

    @property
    def is_done(self) -> bool:
        return self.category is StatusCategory.DONE

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "category": self.category.value}


@dataclass(frozen=True)
class WorkflowTransition:
    """A guarded edge between statuses.

    ``from_statuses`` empty means *global*: the transition can fire from any status
    (the Jira "All" transition, e.g. a universal "Cancel"). ``conditions`` are names
    resolved against :data:`CONDITION_REGISTRY` and must **all** pass.
    ``post_functions`` are opaque names the application applies after the move
    (e.g. ``"assign_to_actor"``, ``"set_resolution"``, ``"stamp_resolved_at"``).
    """

    id: str
    name: str
    to_status: str
    from_statuses: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    post_functions: tuple[str, ...] = ()

    @property
    def is_global(self) -> bool:
        return not self.from_statuses

    def applies_from(self, status_id: str) -> bool:
        return self.is_global or status_id in self.from_statuses

    def conditions_met(self, context: Mapping[str, Any]) -> bool:
        for name in self.conditions:
            predicate = CONDITION_REGISTRY.get(name)
            if predicate is not None and not predicate(context):
                return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "to_status": self.to_status,
            "from_statuses": list(self.from_statuses),
            "global": self.is_global,
            "conditions": list(self.conditions),
            "post_functions": list(self.post_functions),
        }


@dataclass
class TransitionOutcome:
    """Result of applying a transition: the new status and the post-functions to run."""

    transition: WorkflowTransition
    from_status: str
    to_status: str
    post_functions: tuple[str, ...]


@dataclass
class WorkflowScheme:
    """A customizable workflow: statuses + guarded transitions + an initial status.

    Build one fluently::

        scheme = (
            WorkflowScheme("incident", "Incident Management")
            .add_status("open", "Open", StatusCategory.TODO, initial=True)
            .add_status("in_progress", "In Progress", StatusCategory.IN_PROGRESS)
            .add_status("resolved", "Resolved", StatusCategory.DONE)
            .add_transition("start", "Start Progress", "in_progress", ["open"])
            .add_transition("resolve", "Resolve", "resolved", ["in_progress"],
                            post_functions=["stamp_resolved_at"])
        )
    """

    key: str
    name: str
    description: str = ""
    statuses: dict[str, WorkflowStatus] = field(default_factory=dict)
    transitions: dict[str, WorkflowTransition] = field(default_factory=dict)
    initial_status_id: str = ""

    # -- builder API -------------------------------------------------------

    def add_status(
        self,
        status_id: str,
        name: str,
        category: StatusCategory = StatusCategory.TODO,
        *,
        initial: bool = False,
    ) -> WorkflowScheme:
        status = WorkflowStatus(id=status_id, name=name, category=category)
        self.statuses[status_id] = status
        if initial or not self.initial_status_id:
            self.initial_status_id = status_id
        return self

    def add_transition(
        self,
        transition_id: str,
        name: str,
        to_status: str,
        from_statuses: list[str] | tuple[str, ...] = (),
        *,
        conditions: list[str] | tuple[str, ...] = (),
        post_functions: list[str] | tuple[str, ...] = (),
    ) -> WorkflowScheme:
        self.transitions[transition_id] = WorkflowTransition(
            id=transition_id,
            name=name,
            to_status=to_status,
            from_statuses=tuple(from_statuses),
            conditions=tuple(conditions),
            post_functions=tuple(post_functions),
        )
        return self

    # -- queries -----------------------------------------------------------

    def status(self, status_id: str) -> WorkflowStatus:
        try:
            return self.statuses[status_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown status {status_id!r} in scheme {self.key!r}") from exc

    def available_transitions(
        self, from_status_id: str, *, context: Mapping[str, Any] | None = None
    ) -> tuple[WorkflowTransition, ...]:
        """Transitions fireable from ``from_status_id`` whose conditions pass."""

        ctx = context or {}
        return tuple(
            transition
            for transition in self.transitions.values()
            if transition.applies_from(from_status_id)
            and transition.to_status != from_status_id
            and transition.conditions_met(ctx)
        )

    def apply(
        self,
        from_status_id: str,
        transition_id: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> TransitionOutcome:
        """Validate and apply a transition, returning the new status + post-functions."""

        transition = self.transitions.get(transition_id)
        if transition is None:
            raise WorkflowError(f"unknown transition {transition_id!r} in scheme {self.key!r}")
        if not transition.applies_from(from_status_id):
            raise WorkflowError(
                f"transition {transition_id!r} cannot fire from status {from_status_id!r}"
            )
        if transition.to_status not in self.statuses:
            raise WorkflowError(f"transition {transition_id!r} targets unknown status")
        if not transition.conditions_met(context or {}):
            failing = ", ".join(transition.conditions) or "(unknown)"
            raise WorkflowError(f"conditions not met for transition {transition_id!r}: {failing}")
        return TransitionOutcome(
            transition=transition,
            from_status=from_status_id,
            to_status=transition.to_status,
            post_functions=transition.post_functions,
        )

    def reachable_statuses(self) -> set[str]:
        """Statuses reachable from the initial status by any (global-expanded) edge."""

        if not self.initial_status_id:
            return set()
        reachable = {self.initial_status_id}
        queue: deque[str] = deque([self.initial_status_id])
        while queue:
            current = queue.popleft()
            for transition in self.transitions.values():
                if transition.applies_from(current) and transition.to_status not in reachable:
                    reachable.add(transition.to_status)
                    queue.append(transition.to_status)
        return reachable

    def validate(self) -> list[str]:
        """Return structural problems (empty list means the scheme is well-formed)."""

        problems: list[str] = []
        if not self.statuses:
            problems.append("scheme has no statuses")
        if not self.initial_status_id:
            problems.append("scheme has no initial status")
        elif self.initial_status_id not in self.statuses:
            problems.append(f"initial status {self.initial_status_id!r} is not defined")
        for transition in self.transitions.values():
            if transition.to_status not in self.statuses:
                problems.append(
                    f"transition {transition.id!r} targets unknown status {transition.to_status!r}"
                )
            for origin in transition.from_statuses:
                if origin not in self.statuses:
                    problems.append(
                        f"transition {transition.id!r} originates from unknown status {origin!r}"
                    )
            for condition in transition.conditions:
                if condition not in CONDITION_REGISTRY:
                    problems.append(
                        f"transition {transition.id!r} uses unregistered condition {condition!r}"
                    )
        if self.statuses and self.initial_status_id in self.statuses:
            unreachable = set(self.statuses) - self.reachable_statuses()
            for status_id in sorted(unreachable):
                problems.append(f"status {status_id!r} is unreachable from the initial status")
        if not any(s.is_done for s in self.statuses.values()):
            problems.append("scheme has no terminal (Done) status")
        return problems

    @property
    def is_valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "initial_status_id": self.initial_status_id,
            "statuses": [status.as_dict() for status in self.statuses.values()],
            "transitions": [transition.as_dict() for transition in self.transitions.values()],
            "valid": self.is_valid,
            "problems": self.validate(),
        }


def resolved_edges(scheme: WorkflowScheme) -> list[tuple[str, WorkflowTransition, str]]:
    """Expand global transitions to concrete ``(from, transition, to)`` triples.

    Diagram exporters need explicit endpoints, so a global transition becomes one
    edge from every status (except its own target) — the fully-expanded form of a
    Jira "All" transition.
    """

    edges: list[tuple[str, WorkflowTransition, str]] = []
    for transition in scheme.transitions.values():
        origins = (
            transition.from_statuses
            if transition.from_statuses
            else tuple(s for s in scheme.statuses if s != transition.to_status)
        )
        for origin in origins:
            if origin in scheme.statuses and transition.to_status in scheme.statuses:
                edges.append((origin, transition, transition.to_status))
    return edges
