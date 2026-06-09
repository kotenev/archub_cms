"""Platform-owned SQL repositories for the ITSM Service Desk plugin."""

from __future__ import annotations

__all__ = ["PostgresRequestRepository", "SqliteRequestRepository"]

from archub_cms.extensibility.example_plugins.itsm.repository import (
    RequestRepository,
    _request_from_row,
    _request_to_row,
)
from archub_cms.extensibility.example_plugins.itsm.request import Request
from archub_cms.extensibility.platform_adapter import PostgresPluginStore, SQLitePluginStore

_CREATE_REQUEST_TABLE = """
CREATE TABLE IF NOT EXISTS itsm_request (
    key TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    summary TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    scheme_key TEXT NOT NULL,
    status_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    reporter TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT '',
    cloud_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL DEFAULT 0,
    resolution TEXT NOT NULL DEFAULT '',
    resolved_at REAL,
    sla_response_due REAL,
    sla_resolution_due REAL,
    history_json TEXT NOT NULL DEFAULT '[]'
)
"""

_CREATE_SEQ_TABLE = """
CREATE TABLE IF NOT EXISTS itsm_request_seq (
    prefix TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_REQUEST_TABLE_PG = """
CREATE TABLE IF NOT EXISTS itsm_request (
    key TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    summary TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    scheme_key TEXT NOT NULL,
    status_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    reporter TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT '',
    cloud_json TEXT NOT NULL DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    resolution TEXT NOT NULL DEFAULT '',
    resolved_at DOUBLE PRECISION,
    sla_response_due DOUBLE PRECISION,
    sla_resolution_due DOUBLE PRECISION,
    history_json TEXT NOT NULL DEFAULT '[]'
)
"""

_CREATE_SEQ_TABLE_PG = """
CREATE TABLE IF NOT EXISTS itsm_request_seq (
    prefix TEXT PRIMARY KEY,
    value BIGINT NOT NULL DEFAULT 0
)
"""


class SqliteRequestRepository(RequestRepository):
    """Persists requests through an audited platform SQLite adapter."""

    def __init__(self, store: SQLitePluginStore) -> None:
        self._store = store
        with self._store.transaction(action="itsm.schema.ensure", target="itsm_request") as conn:
            conn.execute(_CREATE_REQUEST_TABLE)
            conn.execute(_CREATE_SEQ_TABLE)

    @property
    def store(self) -> SQLitePluginStore:
        return self._store

    def next_key(self, prefix: str) -> str:
        value = 0
        with self._store.transaction(action="itsm.request.next_key", target=prefix) as conn:
            conn.execute(
                """
                INSERT INTO itsm_request_seq (prefix, value) VALUES (?, 1)
                ON CONFLICT(prefix) DO UPDATE SET value = value + 1
                """,
                (prefix,),
            )
            row = conn.execute(
                "SELECT value FROM itsm_request_seq WHERE prefix = ?", (prefix,)
            ).fetchone()
            value = int(row["value"])
        return f"{prefix}-{value}"

    def save(self, request: Request) -> None:
        row = _request_to_row(request)
        with self._store.transaction(action="itsm.request.save", target=request.key) as conn:
            conn.execute(
                """
                INSERT INTO itsm_request (
                    key, type, summary, description, scheme_key, status_id, priority,
                    reporter, assignee, cloud_json, created_at, updated_at, resolution,
                    resolved_at, sla_response_due, sla_resolution_due, history_json
                ) VALUES (
                    :key, :type, :summary, :description, :scheme_key, :status_id, :priority,
                    :reporter, :assignee, :cloud_json, :created_at, :updated_at, :resolution,
                    :resolved_at, :sla_response_due, :sla_resolution_due, :history_json
                )
                ON CONFLICT(key) DO UPDATE SET
                    type = excluded.type,
                    summary = excluded.summary,
                    description = excluded.description,
                    scheme_key = excluded.scheme_key,
                    status_id = excluded.status_id,
                    priority = excluded.priority,
                    reporter = excluded.reporter,
                    assignee = excluded.assignee,
                    cloud_json = excluded.cloud_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    resolution = excluded.resolution,
                    resolved_at = excluded.resolved_at,
                    sla_response_due = excluded.sla_response_due,
                    sla_resolution_due = excluded.sla_resolution_due,
                    history_json = excluded.history_json
                """,
                row,
            )

    def get(self, key: str) -> Request | None:
        row = self._store.read(
            action="itsm.request.get",
            target=key,
            callback=lambda conn: conn.execute(
                "SELECT * FROM itsm_request WHERE key = ?", (key,)
            ).fetchone(),
        )
        return _request_from_row(row) if row is not None else None

    def list_all(self) -> list[Request]:
        rows = self._store.read(
            action="itsm.request.list",
            callback=lambda conn: conn.execute(
                "SELECT * FROM itsm_request ORDER BY created_at"
            ).fetchall(),
        )
        return [_request_from_row(row) for row in rows]


class PostgresRequestRepository(RequestRepository):
    """Persists requests through an audited platform PostgreSQL adapter."""

    def __init__(self, store: PostgresPluginStore) -> None:
        self._store = store
        with self._store.transaction(action="itsm.schema.ensure", target="itsm_request") as conn:
            conn.execute(_CREATE_REQUEST_TABLE_PG)
            conn.execute(_CREATE_SEQ_TABLE_PG)

    @property
    def store(self) -> PostgresPluginStore:
        return self._store

    def next_key(self, prefix: str) -> str:
        with self._store.transaction(action="itsm.request.next_key", target=prefix) as conn:
            row = conn.execute(
                """
                INSERT INTO itsm_request_seq (prefix, value) VALUES (%s, 1)
                ON CONFLICT (prefix) DO UPDATE SET value = itsm_request_seq.value + 1
                RETURNING value
                """,
                (prefix,),
            ).fetchone()
            return f"{prefix}-{int(row['value'])}"

    def save(self, request: Request) -> None:
        row = _request_to_row(request)
        with self._store.transaction(action="itsm.request.save", target=request.key) as conn:
            conn.execute(
                """
                INSERT INTO itsm_request (
                    key, type, summary, description, scheme_key, status_id, priority,
                    reporter, assignee, cloud_json, created_at, updated_at, resolution,
                    resolved_at, sla_response_due, sla_resolution_due, history_json
                ) VALUES (
                    %(key)s, %(type)s, %(summary)s, %(description)s, %(scheme_key)s,
                    %(status_id)s, %(priority)s, %(reporter)s, %(assignee)s, %(cloud_json)s,
                    %(created_at)s, %(updated_at)s, %(resolution)s, %(resolved_at)s,
                    %(sla_response_due)s, %(sla_resolution_due)s, %(history_json)s
                )
                ON CONFLICT (key) DO UPDATE SET
                    type = EXCLUDED.type,
                    summary = EXCLUDED.summary,
                    description = EXCLUDED.description,
                    scheme_key = EXCLUDED.scheme_key,
                    status_id = EXCLUDED.status_id,
                    priority = EXCLUDED.priority,
                    reporter = EXCLUDED.reporter,
                    assignee = EXCLUDED.assignee,
                    cloud_json = EXCLUDED.cloud_json,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at,
                    resolution = EXCLUDED.resolution,
                    resolved_at = EXCLUDED.resolved_at,
                    sla_response_due = EXCLUDED.sla_response_due,
                    sla_resolution_due = EXCLUDED.sla_resolution_due,
                    history_json = EXCLUDED.history_json
                """,
                row,
            )

    def get(self, key: str) -> Request | None:
        row = self._store.read(
            action="itsm.request.get",
            target=key,
            callback=lambda conn: conn.execute(
                "SELECT * FROM itsm_request WHERE key = %s", (key,)
            ).fetchone(),
        )
        return _request_from_row(row) if row is not None else None

    def list_all(self) -> list[Request]:
        rows = self._store.read(
            action="itsm.request.list",
            callback=lambda conn: conn.execute(
                "SELECT * FROM itsm_request ORDER BY created_at"
            ).fetchall(),
        )
        return [_request_from_row(row) for row in rows]
