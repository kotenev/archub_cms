"""Projection store: materialized read models rebuilt from domain events.

Projections are denormalized views optimized for specific read patterns
(e.g. "recently published documents", "activity feed", "search index").
Each projection has a name, a version tracking how far it has processed
the event stream, and a JSON payload.
"""

from __future__ import annotations

__all__ = ["ProjectionStore", "SqliteProjectionStore"]

import json
import sqlite3
from typing import Any


class ProjectionStore:
    """Abstract projection store contract."""

    def save(self, name: str, key: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def load(self, name: str, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def load_all(self, name: str, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        raise NotImplementedError

    def delete(self, name: str, key: str) -> bool:
        raise NotImplementedError

    def mark_position(self, name: str, sequence: int) -> None:
        raise NotImplementedError

    def get_position(self, name: str) -> int:
        raise NotImplementedError


class SqliteProjectionStore(ProjectionStore):
    """SQLite-backed projection store with position tracking."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projections (
                name     TEXT NOT NULL,
                key      TEXT NOT NULL,
                payload  TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (name, key)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projection_positions (
                name     TEXT PRIMARY KEY,
                sequence INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def save(self, name: str, key: str, payload: dict[str, Any]) -> None:
        import time

        self._conn.execute(
            "INSERT OR REPLACE INTO projections (name, key, payload, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (name, key, json.dumps(payload, default=str), time.time()),
        )
        self._conn.commit()

    def load(self, name: str, key: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT payload FROM projections WHERE name = ? AND key = ?",
            (name, key),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def load_all(self, name: str, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT payload FROM projections WHERE name = ? ORDER BY updated_at DESC"
            " LIMIT ? OFFSET ?",
            (name, limit, offset),
        )
        return [json.loads(row["payload"]) for row in cursor.fetchall()]

    def delete(self, name: str, key: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM projections WHERE name = ? AND key = ?",
            (name, key),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def mark_position(self, name: str, sequence: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO projection_positions (name, sequence) VALUES (?, ?)",
            (name, sequence),
        )
        self._conn.commit()

    def get_position(self, name: str) -> int:
        cursor = self._conn.execute(
            "SELECT sequence FROM projection_positions WHERE name = ?",
            (name,),
        )
        row = cursor.fetchone()
        return int(row["sequence"]) if row else 0
