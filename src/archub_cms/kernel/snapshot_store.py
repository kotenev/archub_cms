"""Aggregate snapshot store: periodically serializes the full aggregate state
to avoid replaying the entire event stream when reconstituting.

Snapshots are an optimisation for long-lived aggregates with many events.
They coexist with the event store — the aggregate is reconstituted from the
latest snapshot plus any subsequent events.
"""

from __future__ import annotations

__all__ = ["SnapshotStore", "SqliteSnapshotStore"]

import json
import sqlite3
import time
from typing import Any


class SnapshotStore:
    """Abstract snapshot store contract."""

    def save(
        self, aggregate_id: str, aggregate_type: str, state: dict[str, Any], version: int
    ) -> None:
        raise NotImplementedError

    def load_latest(self, aggregate_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class SqliteSnapshotStore(SnapshotStore):
    """SQLite-backed snapshot store."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                aggregate_id    TEXT NOT NULL,
                aggregate_type  TEXT NOT NULL,
                state           TEXT NOT NULL DEFAULT '{}',
                version         INTEGER NOT NULL,
                taken_at        REAL NOT NULL,
                PRIMARY KEY (aggregate_id, version)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_latest ON snapshots(aggregate_id, version DESC)"
        )
        self._conn.commit()

    def save(
        self, aggregate_id: str, aggregate_type: str, state: dict[str, Any], version: int
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO snapshots (aggregate_id, aggregate_type, state, version, taken_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (aggregate_id, aggregate_type, json.dumps(state, default=str), version, time.time()),
        )
        self._conn.commit()

    def load_latest(self, aggregate_id: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT state, version FROM snapshots WHERE aggregate_id = ? ORDER BY version DESC LIMIT 1",
            (aggregate_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        result = json.loads(row["state"])
        result["_snapshot_version"] = row["version"]
        return result
