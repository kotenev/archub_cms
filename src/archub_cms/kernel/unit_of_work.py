"""Unit of Work: a transaction boundary shared by repositories in one use case.

Repositories operate on the connection exposed by an active ``UnitOfWork`` so
that multi-repository commands commit or roll back atomically. The SQLite
implementation collects domain events raised during the transaction and hands
them to an :class:`~archub_cms.kernel.events.EventBus` only *after* a successful
commit (events never fire for rolled-back work).
"""

from __future__ import annotations

__all__ = ["SqliteUnitOfWork", "UnitOfWork"]

import sqlite3
from collections.abc import Callable
from types import TracebackType
from typing import Protocol

from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus


class UnitOfWork(Protocol):
    connection: sqlite3.Connection

    def collect(self, *events: ArcHubDomainEvent) -> None: ...

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool: ...


class SqliteUnitOfWork:
    """Concrete unit of work over a single sqlite3 connection."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        *,
        event_bus: EventBus | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._event_bus = event_bus or get_event_bus()
        self._pending: list[ArcHubDomainEvent] = []
        self.connection: sqlite3.Connection = None  # type: ignore[assignment]

    def collect(self, *events: ArcHubDomainEvent) -> None:
        self._pending.extend(events)

    def __enter__(self) -> SqliteUnitOfWork:
        self.connection = self._connection_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
        if exc_type is None:
            events, self._pending = self._pending, []
            for event in events:
                self._event_bus.publish(event)
        else:
            self._pending.clear()
        return False
