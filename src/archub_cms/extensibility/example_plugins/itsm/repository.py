"""Persistence for service-desk requests: SQLite, PostgreSQL or in-memory.

Plugins run sandboxed with no database handle from the :class:`PluginContext`, so
the ITSM plugin owns its storage. Three interchangeable adapters satisfy the
:class:`RequestRepository` port:

* :class:`SqliteRequestRepository` — the zero-dependency default; keeps requests in
  an ``itsm_request`` table (with a monotonic key sequence per project prefix) in
  whatever SQLite path the plugin is configured with (the shared ArcHub file by
  default).
* :class:`PostgresRequestRepository` — the same schema on PostgreSQL for multi-node
  deployments; the ``psycopg`` driver is imported lazily so it stays optional.
* :class:`InMemoryRequestRepository` — fast, dependency-free, for unit tests and as a
  sandbox fallback.

The row mapping (:func:`_request_to_row` / :func:`_request_from_row`) is shared by all
backends, so request semantics stay identical regardless of where the data lives.
"""

from __future__ import annotations

__all__ = [
    "InMemoryRequestRepository",
    "PostgresDatabase",
    "PostgresRequestRepository",
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

# PostgreSQL uses the same logical schema; only the float type and the parameter
# placeholder style differ from SQLite, so the row mapping is fully reused.
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


class PostgresDatabase:
    """Connection factory for a PostgreSQL ITSM store (psycopg 3, lazily imported)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @property
    def dsn(self) -> str:
        return self._dsn

    def connect(self) -> Any:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:  # optional dependency
            raise RuntimeError(
                "PostgreSQL storage requires the 'psycopg' driver "
                "(install archub-cms[postgres] or `pip install psycopg[binary]`)"
            ) from exc
        return psycopg.connect(self._dsn, row_factory=dict_row)


class PostgresRequestRepository:
    """Persists requests in the ``itsm_request`` table of a PostgreSQL database.

    Mirrors :class:`SqliteRequestRepository` exactly — same columns, same monotonic
    ``PREFIX-N`` sequence and the same shared row mapping — so a deployment can switch
    backends without any change in request behaviour. Uses psycopg's ``%(name)s``
    parameter style and ``RETURNING`` for the sequence.
    """

    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database
        conn = self._db.connect()
        try:
            conn.execute(_CREATE_REQUEST_TABLE_PG)
            conn.execute(_CREATE_SEQ_TABLE_PG)
            conn.commit()
        finally:
            conn.close()

    def next_key(self, prefix: str) -> str:
        conn = self._db.connect()
        try:
            row = conn.execute(
                """
                INSERT INTO itsm_request_seq (prefix, value) VALUES (%s, 1)
                ON CONFLICT (prefix) DO UPDATE SET value = itsm_request_seq.value + 1
                RETURNING value
                """,
                (prefix,),
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
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Request | None:
        conn = self._db.connect()
        try:
            row = conn.execute("SELECT * FROM itsm_request WHERE key = %s", (key,)).fetchone()
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
