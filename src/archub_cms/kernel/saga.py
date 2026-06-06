"""Saga / Process Manager pattern for coordinating long-running cross-context workflows.

A saga orchestrates multi-step operations that span bounded contexts
(e.g. "publish content → notify watchers → refresh search index → trigger
webhooks") without tight coupling. Each step is driven by the completion of the
previous step's domain event, so contexts remain independently testable.

This is the process-manager variant: the saga is stateful, tracks its own
progress, and decides the next step based on the current state and incoming
event.
"""

from __future__ import annotations

__all__ = [
    "Saga",
    "SagaContext",
    "SagaDefinition",
    "SagaStep",
    "SagaStatus",
    "SimpleSagaRunner",
]

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from archub_cms.kernel.events import ArcHubDomainEvent, EventBus


class SagaStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"


@dataclass(frozen=True)
class SagaContext:
    """Shared mutable state bag passed between saga steps."""

    saga_id: str
    saga_type: str
    status: SagaStatus = SagaStatus.PENDING
    current_step: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def with_data(self, **kwargs: Any) -> SagaContext:
        merged = {**self.data, **kwargs}
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=self.status,
            current_step=self.current_step,
            data=merged,
            errors=self.errors,
        )

    def advance(self) -> SagaContext:
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=SagaStatus.RUNNING,
            current_step=self.current_step + 1,
            data=self.data,
            errors=self.errors,
        )

    def complete(self) -> SagaContext:
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=SagaStatus.COMPLETED,
            current_step=self.current_step,
            data=self.data,
            errors=self.errors,
        )

    def fail(self, error: str) -> SagaContext:
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=SagaStatus.FAILED,
            current_step=self.current_step,
            data=self.data,
            errors=(*self.errors, error),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "saga_id": self.saga_id,
            "saga_type": self.saga_type,
            "status": self.status.value,
            "current_step": self.current_step,
            "data": dict(self.data),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class SagaStep:
    """One step in a saga: reacts to an event type and optionally triggers an action."""

    name: str
    reacts_to: str
    action: Callable[[SagaContext, ArcHubDomainEvent], SagaContext] | None = None
    compensate: Callable[[SagaContext], SagaContext] | None = None


@dataclass(frozen=True)
class SagaDefinition:
    """Declarative saga blueprint: a sequence of steps triggered by events."""

    saga_type: str
    trigger_event: str
    steps: tuple[SagaStep, ...]

    @property
    def step_count(self) -> int:
        return len(self.steps)


class Saga(ABC):
    """Base class for sagas that the runner invokes."""

    @abstractmethod
    def definition(self) -> SagaDefinition: ...

    @abstractmethod
    def initial_context(self, saga_id: str) -> SagaContext: ...


class SimpleSagaRunner:
    """Runs sagas by subscribing their steps to the event bus.

    When the trigger event arrives, the saga context is created. Subsequent
    steps advance as their ``reacts_to`` events arrive. If a step action raises,
    the saga is marked FAILED and any compensating actions run in reverse order.
    """

    def __init__(self, *, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus or EventBus()
        self._active: dict[str, tuple[Saga, SagaContext]] = {}

    def register(self, saga: Saga) -> None:
        defn = saga.definition()
        self._bus.subscribe(defn.trigger_event, self._make_trigger(saga))
        for step in defn.steps:
            self._bus.subscribe(step.reacts_to, self._make_step_handler(saga, step))

    def active_sagas(self) -> list[dict[str, Any]]:
        return [
            {"saga_id": ctx.saga_id, "saga_type": ctx.saga_type, "status": ctx.status.value}
            for ctx in (ctx for _, ctx in self._active.values())
        ]

    def _make_trigger(self, saga: Saga) -> Callable[[ArcHubDomainEvent], None]:
        def handler(event: ArcHubDomainEvent) -> None:
            ctx = saga.initial_context(event.aggregate_id)
            ctx = SagaContext(
                saga_id=ctx.saga_id,
                saga_type=ctx.saga_type,
                status=SagaStatus.RUNNING,
                current_step=0,
                data={**ctx.data, "trigger_event": event.event_type},
            )
            self._active[ctx.saga_id] = (saga, ctx)

        return handler

    def _make_step_handler(self, saga: Saga, step: SagaStep) -> Callable[[ArcHubDomainEvent], None]:
        def handler(event: ArcHubDomainEvent) -> None:
            matches = [
                (sid, (s, ctx))
                for sid, (s, ctx) in self._active.items()
                if s is saga and ctx.status == SagaStatus.RUNNING
            ]
            for saga_id, (_, ctx) in matches:
                if step.action:
                    try:
                        ctx = step.action(ctx, event)
                    except Exception as exc:
                        ctx = ctx.fail(str(exc))
                        self._compensate(saga, ctx)
                ctx = ctx.advance()
                if ctx.current_step >= saga.definition().step_count:
                    ctx = ctx.complete()
                self._active[saga_id] = (saga, ctx)

        return handler

    def _compensate(self, saga: Saga, ctx: SagaContext) -> None:
        import contextlib

        defn = saga.definition()
        for step in reversed(defn.steps[: ctx.current_step]):
            if step.compensate:
                with contextlib.suppress(Exception):
                    step.compensate(ctx)
