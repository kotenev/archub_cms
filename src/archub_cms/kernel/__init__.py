"""Shared DDD building blocks for ArcHub bounded contexts.

The kernel holds framework-agnostic primitives reused across every context:
domain events + an in-process event bus, a unit-of-work transaction boundary,
a typed ``Result`` for explicit error handling, and the ``Specification``
pattern for composable query filters.
"""

from __future__ import annotations

from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, content_event, get_event_bus
from archub_cms.kernel.result import Err, Ok, Result
from archub_cms.kernel.specification import AndSpecification, NotSpecification, Specification
from archub_cms.kernel.unit_of_work import SqliteUnitOfWork, UnitOfWork

__all__ = [
    "AndSpecification",
    "ArcHubDomainEvent",
    "Err",
    "EventBus",
    "NotSpecification",
    "Ok",
    "Result",
    "Specification",
    "SqliteUnitOfWork",
    "UnitOfWork",
    "content_event",
    "get_event_bus",
]
