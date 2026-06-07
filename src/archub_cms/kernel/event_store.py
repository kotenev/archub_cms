"""Persistent event store for event-sourced aggregates.

Appends domain events to a durable log keyed by aggregate id and sequence
number. Supports reconstituting an aggregate from its full event history and
provides a typed replay API for projections.
"""

from __future__ import annotations

__all__ = ["EventStore", "SqliteEventStore"]

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from archub_cms.kernel.events import ArcHubDomainEvent


class EventStore:
    """Abstract event store contract."""

    def append(self, event: ArcHubDomainEvent, *, sequence: int = 0) -> None:
        raise NotImplementedError

    def load(self, aggregate_id: str) -> list[ArcHubDomainEvent]:
        raise NotImplementedError

    def load_from(self, aggregate_id: str, after_sequence: int) -> list[ArcHubDomainEvent]:
        raise NotImplementedError

    def load_all_after(self, after_sequence: int, *, limit: int = 100) -> list[ArcHubDomainEvent]:
        raise NotImplementedError

    def latest_sequence(self, aggregate_id: str) -> int:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """A persisted domain event with storage metadata."""

    sequence: int
    aggregate_id: str
    event_type: str
    actor: str
    metadata: dict[str, Any]
    stored_at: float

    def to_domain_event(self) -> ArcHubDomainEvent:
        return ArcHubDomainEvent(
            event_type=self.event_type,
            aggregate_id=self.aggregate_id,
            actor=self.actor,
            metadata=self.metadata,
        )


class SqliteEventStore(EventStore):
    """SQLite-backed event store with a single ``domain_events`` table."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS domain_events (
                sequence      INTEGER PRIMARY KEY AUTOINCREMENT,
                aggregate_id  TEXT    NOT NULL,
                event_type    TEXT    NOT NULL,
                actor         TEXT    NOT NULL DEFAULT '',
                metadata      TEXT    NOT NULL DEFAULT '{}',
                stored_at     REAL    NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_aggregate ON domain_events(aggregate_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type ON domain_events(event_type)"
        )
        self._conn.commit()

    def append(self, event: ArcHubDomainEvent, *, sequence: int = 0) -> None:
        self._conn.execute(
            "INSERT INTO domain_events (aggregate_id, event_type, actor, metadata, stored_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                event.aggregate_id,
                event.event_type,
                event.actor,
                json.dumps(event.metadata, default=str),
                time.time(),
            ),
        )
        self._conn.commit()

    def append_many(self, events: list[ArcHubDomainEvent]) -> None:
        if not events:
            return
        rows = [
            (
                e.aggregate_id,
                e.event_type,
                e.actor,
                json.dumps(e.metadata, default=str),
                time.time(),
            )
            for e in events
        ]
        self._conn.executemany(
            "INSERT INTO domain_events (aggregate_id, event_type, actor, metadata, stored_at)"
            " VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def load(self, aggregate_id: str) -> list[ArcHubDomainEvent]:
        cursor = self._conn.execute(
            "SELECT aggregate_id, event_type, actor, metadata"
            " FROM domain_events WHERE aggregate_id = ? ORDER BY sequence",
            (aggregate_id,),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def load_from(self, aggregate_id: str, after_sequence: int) -> list[ArcHubDomainEvent]:
        cursor = self._conn.execute(
            "SELECT aggregate_id, event_type, actor, metadata"
            " FROM domain_events WHERE aggregate_id = ? AND sequence > ? ORDER BY sequence",
            (aggregate_id, after_sequence),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def load_all_after(self, after_sequence: int, *, limit: int = 100) -> list[ArcHubDomainEvent]:
        cursor = self._conn.execute(
            "SELECT aggregate_id, event_type, actor, metadata"
            " FROM domain_events WHERE sequence > ? ORDER BY sequence LIMIT ?",
            (after_sequence, limit),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def latest_sequence(self, aggregate_id: str) -> int:
        cursor = self._conn.execute(
            "SELECT MAX(sequence) FROM domain_events WHERE aggregate_id = ?",
            (aggregate_id,),
        )
        row = cursor.fetchone()
        return int(row[0] or 0)

    def global_sequence(self) -> int:
        cursor = self._conn.execute("SELECT MAX(sequence) FROM domain_events")
        row = cursor.fetchone()
        return int(row[0] or 0)

    def _row_to_event(self, row: sqlite3.Row) -> ArcHubDomainEvent:
        return ArcHubDomainEvent(
            event_type=row["event_type"],
            aggregate_id=row["aggregate_id"],
            actor=row["actor"],
            metadata=json.loads(row["metadata"]),
        )
