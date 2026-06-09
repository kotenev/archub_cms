"""The Service Desk domain: tickets, priorities, SLA policies and cloud context.

A :class:`Ticket` is the aggregate the workflow engine drives. It carries a
cloud-provider :class:`CloudResource` context (so an incident can be raised against
a specific managed service in a region) and SLA due-times derived from an
:class:`SlaPolicy`, recording every state change in its :attr:`Ticket.history`.
"""

from __future__ import annotations

__all__ = [
    "CloudResource",
    "Priority",
    "SlaPolicy",
    "Ticket",
    "TicketEvent",
    "TicketType",
]

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

_MINUTE = 60.0

# Priority ordering, low → critical, used for SLA lookups and triage scoring.
_PRIORITY_ORDER = ("low", "medium", "high", "critical")


class TicketType(StrEnum):
    """ITIL-aligned Service Desk request types."""

    INCIDENT = "incident"
    SERVICE_REQUEST = "service_request"
    PROBLEM = "problem"
    CHANGE = "change"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _PRIORITY_ORDER.index(self.value)


@dataclass(frozen=True)
class CloudResource:
    """The cloud-provider object a ticket concerns (provider / service / region)."""

    provider: str = ""
    service: str = ""
    region: str = ""
    resource_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "service": self.service,
            "region": self.region,
            "resource_id": self.resource_id,
        }


@dataclass(frozen=True)
class SlaPolicy:
    """Per-priority response/resolution targets, in minutes."""

    name: str = "standard"
    # priority value -> (response_minutes, resolution_minutes)
    targets: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {
            "critical": (15, 240),
            "high": (30, 480),
            "medium": (120, 1440),
            "low": (480, 4320),
        }
    )

    def response_minutes(self, priority: Priority) -> int:
        return self.targets.get(priority.value, (120, 1440))[0]

    def resolution_minutes(self, priority: Priority) -> int:
        return self.targets.get(priority.value, (120, 1440))[1]


@dataclass(frozen=True)
class TicketEvent:
    """An immutable entry in a ticket's audit history."""

    at: float
    actor: str
    kind: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"at": self.at, "actor": self.actor, "kind": self.kind, "detail": self.detail}


@dataclass
class Ticket:
    """A Service Desk ticket driven through a customizable workflow scheme."""

    key: str
    type: TicketType
    summary: str
    scheme_key: str
    status_id: str
    priority: Priority = Priority.MEDIUM
    description: str = ""
    reporter: str = ""
    assignee: str = ""
    cloud: CloudResource = field(default_factory=CloudResource)
    created_at: float = 0.0
    updated_at: float = 0.0
    resolution: str = ""
    resolved_at: float | None = None
    sla_response_due: float | None = None
    sla_resolution_due: float | None = None
    history: list[TicketEvent] = field(default_factory=list)

    def record(self, event: TicketEvent) -> None:
        self.history.append(event)
        self.updated_at = event.at

    def response_breached(self, now: float) -> bool:
        if self.sla_response_due is None:
            return False
        # Considered met once an agent is assigned (first response proxy).
        return not self.assignee and now > self.sla_response_due

    def resolution_breached(self, now: float) -> bool:
        if self.sla_resolution_due is None or self.resolved_at is not None:
            return False
        return now > self.sla_resolution_due

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "type": self.type.value,
            "summary": self.summary,
            "description": self.description,
            "scheme_key": self.scheme_key,
            "status_id": self.status_id,
            "priority": self.priority.value,
            "reporter": self.reporter,
            "assignee": self.assignee,
            "cloud": self.cloud.as_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at,
            "sla_response_due": self.sla_response_due,
            "sla_resolution_due": self.sla_resolution_due,
            "history": [event.as_dict() for event in self.history],
        }
