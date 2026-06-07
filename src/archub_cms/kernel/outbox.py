"""Transactional outbox: stores pending integration events inside the
write transaction so at-least-once delivery is guaranteed even if the
downstream consumer is temporarily unavailable.

The outbox pattern bridges domain events and external systems (webhooks,
message brokers, search indexers) without requiring distributed transactions.
"""

from __future__ import annotations

__all__ = ["OutboxEntry", "OutboxStore", "SqliteOutboxStore"]

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OutboxEntry:
    """A single pending outbox message."""

    entry_id: int
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: float
    dispatched: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "aggregate_id": self.aggregate_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "dispatched": self.dispatched,
        }


class OutboxStore:
    """Abstract outbox store contract."""

    def append(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> int:
        raise NotImplementedError

    def pending(self, *, limit: int = 100) -> list[OutboxEntry]:
        raise NotImplementedError

    def mark_dispatched(self, entry_ids: tuple[int, ...]) -> None:
        raise NotImplementedError


class SqliteOutboxStore(OutboxStore):
    """SQLite-backed outbox store."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                entry_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                aggregate_id  TEXT    NOT NULL,
                event_type    TEXT    NOT NULL,
                payload       TEXT    NOT NULL DEFAULT '{}',
                created_at    REAL    NOT NULL,
                dispatched    INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(dispatched, created_at)"
        )
        self._conn.commit()

    def append(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> int:
        cursor = self._conn.execute(
            "INSERT INTO outbox (aggregate_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
            (aggregate_id, event_type, json.dumps(payload, default=str), time.time()),
        )
        self._conn.commit()
        return int(cursor.lastrowid or 0)

    def pending(self, *, limit: int = 100) -> list[OutboxEntry]:
        cursor = self._conn.execute(
            "SELECT entry_id, aggregate_id, event_type, payload, created_at, dispatched"
            " FROM outbox WHERE dispatched = 0 ORDER BY created_at LIMIT ?",
            (limit,),
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def mark_dispatched(self, entry_ids: tuple[int, ...]) -> None:
        if not entry_ids:
            return
        placeholders = ",".join("?" for _ in entry_ids)
        self._conn.execute(
            f"UPDATE outbox SET dispatched = 1 WHERE entry_id IN ({placeholders})",
            entry_ids,
        )
        self._conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> OutboxEntry:
        return OutboxEntry(
            entry_id=row["entry_id"],
            aggregate_id=row["aggregate_id"],
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
            dispatched=bool(row["dispatched"]),
        )
