"""Shared DDD building blocks for ArcHub bounded contexts.

The kernel holds framework-agnostic primitives reused across every context:
domain events + an in-process event bus, a unit-of-work transaction boundary,
a typed ``Result`` for explicit error handling, the ``Specification`` pattern
for composable query filters, a CQRS ``Mediator``, ``AggregateRoot`` base class,
shared value objects (Identity, Timestamp, Pagination, Page), a saga/process-manager
framework, an event store for event sourcing, a projection store for materialized
read models, a transactional outbox, a snapshot store, a domain service registry,
a health check subsystem, a retry policy, and an async command bus.
"""

from __future__ import annotations

from archub_cms.kernel.aggregate_root import AggregateRoot
from archub_cms.kernel.async_command_bus import AsyncCommandBus, QueuedCommand
from archub_cms.kernel.circuit_breaker import CircuitBreaker, CircuitState
from archub_cms.kernel.domain_registry import DomainRegistry, get_domain_registry
from archub_cms.kernel.event_store import EventStore, SqliteEventStore
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, content_event, get_event_bus
from archub_cms.kernel.health_check import (
    HealthCheckResult,
    HealthCheckService,
    get_health_check_service,
)
from archub_cms.kernel.mediator import Command, Mediator, Query, get_mediator
from archub_cms.kernel.outbox import OutboxEntry, OutboxStore, SqliteOutboxStore
from archub_cms.kernel.projection_store import ProjectionStore, SqliteProjectionStore
from archub_cms.kernel.result import Err, Ok, Result
from archub_cms.kernel.retry_policy import RetryPolicy, RetryResult
from archub_cms.kernel.saga import (
    Saga,
    SagaContext,
    SagaDefinition,
    SagaStatus,
    SagaStep,
    SimpleSagaRunner,
)
from archub_cms.kernel.snapshot_store import SnapshotStore, SqliteSnapshotStore
from archub_cms.kernel.specification import AndSpecification, NotSpecification, Specification
from archub_cms.kernel.unit_of_work import SqliteUnitOfWork, UnitOfWork
from archub_cms.kernel.value_objects import Identity, Page, Pagination, Timestamp

__all__ = [
    "AggregateRoot",
    "AndSpecification",
    "ArcHubDomainEvent",
    "AsyncCommandBus",
    "CircuitBreaker",
    "CircuitState",
    "Command",
    "DomainRegistry",
    "Err",
    "EventBus",
    "EventStore",
    "HealthCheckResult",
    "HealthCheckService",
    "Identity",
    "Mediator",
    "NotSpecification",
    "Ok",
    "OutboxEntry",
    "OutboxStore",
    "Page",
    "Pagination",
    "ProjectionStore",
    "Query",
    "QueuedCommand",
    "Result",
    "RetryPolicy",
    "RetryResult",
    "Saga",
    "SagaContext",
    "SagaDefinition",
    "SagaStep",
    "SagaStatus",
    "SimpleSagaRunner",
    "SnapshotStore",
    "Specification",
    "SqliteEventStore",
    "SqliteOutboxStore",
    "SqliteProjectionStore",
    "SqliteSnapshotStore",
    "SqliteUnitOfWork",
    "Timestamp",
    "UnitOfWork",
    "content_event",
    "get_domain_registry",
    "get_event_bus",
    "get_health_check_service",
    "get_mediator",
]
