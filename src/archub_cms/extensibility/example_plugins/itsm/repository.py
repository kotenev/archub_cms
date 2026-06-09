"""Persistence for service-desk requests: a SQLite repository + an in-memory one.

Plugins run sandboxed with no database handle from the :class:`PluginContext`, so
the ITSM plugin owns its storage: :class:`SqliteRequestRepository` keeps requests
in an ``itsm_request`` table (with a monotonic key sequence per project prefix) in
whatever database path the plugin is configured with — by default the shared ArcHub
SQLite file. :class:`InMemoryRequestRepository` is the fast, dependency-free variant
used by unit tests and as a sandbox fallback. Both satisfy :class:`RequestRepository`.
"""

from __future__ import annotations

__all__ = [
    "InMemoryRequestRepository",
    "RequestRepository",
    "SqliteRequestRepository",
]

import json
from typing import Any, Protocol, runtime_checkable

from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    Request,
    RequestEvent,
    RequestType,
)
from archub_cms.infrastructure.db.database import Database

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


@runtime_checkable
class RequestRepository(Protocol):
    """Storage port for service-desk requests."""

    def next_key(self, prefix: str) -> str:
        """Allocate the next ``PREFIX-N`` reference for a new request."""

    def save(self, request: Request) -> None:
        """Insert or update a request (full row replace)."""

    def get(self, key: str) -> Request | None: ...

    def list_all(self) -> list[Request]: ...


def _request_to_row(request: Request) -> dict[str, Any]:
    return {
        "key": request.key,
        "type": request.type.value,
        "summary": request.summary,
        "description": request.description,
        "scheme_key": request.scheme_key,
        "status_id": request.status_id,
        "priority": request.priority.value,
        "reporter": request.reporter,
        "assignee": request.assignee,
        "cloud_json": json.dumps(request.cloud.as_dict(), ensure_ascii=False),
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "resolution": request.resolution,
        "resolved_at": request.resolved_at,
        "sla_response_due": request.sla_response_due,
        "sla_resolution_due": request.sla_resolution_due,
        "history_json": json.dumps(
            [event.as_dict() for event in request.history], ensure_ascii=False
        ),
    }


def _request_from_row(row: Any) -> Request:
    try:
        cloud_payload = json.loads(row["cloud_json"] or "{}")
    except (ValueError, TypeError):
        cloud_payload = {}
    try:
        history_payload = json.loads(row["history_json"] or "[]")
    except (ValueError, TypeError):
        history_payload = []
    return Request(
        key=str(row["key"]),
        type=RequestType(str(row["type"])),
        summary=str(row["summary"]),
        scheme_key=str(row["scheme_key"]),
        status_id=str(row["status_id"]),
        priority=Priority(str(row["priority"])),
        description=str(row["description"] or ""),
        reporter=str(row["reporter"] or ""),
        assignee=str(row["assignee"] or ""),
        cloud=CloudResource(
            provider=str(cloud_payload.get("provider") or ""),
            service=str(cloud_payload.get("service") or ""),
            region=str(cloud_payload.get("region") or ""),
            resource_id=str(cloud_payload.get("resource_id") or ""),
        ),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        resolution=str(row["resolution"] or ""),
        resolved_at=row["resolved_at"],
        sla_response_due=row["sla_response_due"],
        sla_resolution_due=row["sla_resolution_due"],
        history=[
            RequestEvent.from_dict(item) for item in history_payload if isinstance(item, dict)
        ],
    )


class SqliteRequestRepository:
    """Persists requests in the ``itsm_request`` table of an ArcHub SQLite database."""

    def __init__(self, database: Database) -> None:
        self._db = database
        conn = self._db.connect()
        try:
            conn.execute(_CREATE_REQUEST_TABLE)
            conn.execute(_CREATE_SEQ_TABLE)
            conn.commit()
        finally:
            conn.close()

    def next_key(self, prefix: str) -> str:
        conn = self._db.connect()
        try:
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
            conn.commit()
            return f"{prefix}-{int(row['value'])}"
        finally:
            conn.close()

    def save(self, request: Request) -> None:
        row = _request_to_row(request)
        conn = self._db.connect()
        try:
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
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Request | None:
        conn = self._db.connect()
        try:
            row = conn.execute("SELECT * FROM itsm_request WHERE key = ?", (key,)).fetchone()
            return _request_from_row(row) if row is not None else None
        finally:
            conn.close()

    def list_all(self) -> list[Request]:
        conn = self._db.connect()
        try:
            rows = conn.execute("SELECT * FROM itsm_request ORDER BY created_at").fetchall()
            return [_request_from_row(row) for row in rows]
        finally:
            conn.close()


class InMemoryRequestRepository:
    """Process-local request store — fast unit tests and a no-database fallback."""

    def __init__(self) -> None:
        self._rows: dict[str, Request] = {}
        self._seq: dict[str, int] = {}

    def next_key(self, prefix: str) -> str:
        self._seq[prefix] = self._seq.get(prefix, 0) + 1
        return f"{prefix}-{self._seq[prefix]}"

    def save(self, request: Request) -> None:
        # Store a detached copy so external mutation does not bypass save().
        self._rows[request.key] = _request_from_row_dict(_request_to_row(request))

    def get(self, key: str) -> Request | None:
        stored = self._rows.get(key)
        return _request_from_row_dict(_request_to_row(stored)) if stored is not None else None

    def list_all(self) -> list[Request]:
        return [
            _request_from_row_dict(_request_to_row(request))
            for request in sorted(self._rows.values(), key=lambda r: r.created_at)
        ]


def _request_from_row_dict(row: dict[str, Any]) -> Request:
    """Reconstruct a Request from the same dict shape the SQLite row uses."""

    return _request_from_row(row)
